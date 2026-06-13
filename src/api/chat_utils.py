import json
import queue
import asyncio
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, messages_to_dict, messages_from_dict
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.types import Command

from src.graph.graph import get_graph
from src.utils.logger import get_logger
from src.db.postgres import get_db_cursor
from src.config.settings import settings

logger = get_logger("chat_utils")

# Initialize LangGraph instance
graph = get_graph()


def format_messages(messages):
    """Formats messages for the frontend API response."""
    formatted = []
    for m in messages:
        if m.type == "human":
            role = "user"
        elif m.type == "ai":
            role = "assistant"
        else:
            role = m.type  # e.g. "tool"

        formatted.append({
            "role": role,
            "content": getattr(m, "content", str(m))
        })
    return formatted


def get_active_interrupt(snapshot):
    """Extracts pending confirmation interrupts from the graph state snapshot."""
    if snapshot.tasks:
        for task in snapshot.tasks:
            if task.interrupts:
                return task.interrupts[0].value
                
    # Fallback for Redis checkpointer where tasks/interrupts might not be serialized correctly
    if snapshot.next:
        next_node = snapshot.next[0] if isinstance(snapshot.next, tuple) else snapshot.next
        if next_node == "confirm_node":
            draft = snapshot.values.get("booking_draft")
            if draft and draft.get("status") == "pending":
                return {
                    "message": "Confirm your booking?",
                    "data": draft,
                    "options": ["Approve", "Reject"]
                }
        elif next_node == "cancel_confirm_node":
            cancel_draft = snapshot.values.get("cancel_draft")
            if cancel_draft and cancel_draft.get("status") != "cancelled":
                return {
                    "message": f"Cancel booking for {cancel_draft['show_date']} at {cancel_draft['show_time']}? "
                               f"Refund: ₹{cancel_draft['refund_amount']} ({cancel_draft['refund_message']})",
                    "data": cancel_draft,
                    "options": ["Approve", "Reject"]
                }
    return None


def save_messages_to_postgress(user_id: str, thread_id: str, messages: list):
    """Serialize and append new chat messages for a session to Supabase using JSONB concatenation."""
    if not messages:
        return
    try:
        serialized_messages = messages_to_dict(messages)
        with get_db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_messages (user_id, thread_id, messages, updated_at)
                VALUES (%s, %s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, thread_id) DO UPDATE
                SET messages = chat_messages.messages || EXCLUDED.messages,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (user_id, thread_id, json.dumps(serialized_messages))
            )
        logger.info(f"Appended {len(messages)} messages to Supabase for user={user_id}, thread={thread_id}")
    except Exception as e:
        logger.error(f"Failed to save messages to Supabase: {e}", exc_info=True)


def load_messages_from_postgress(user_id: str, thread_id: str) -> list:
    """Load and deserialize chat history for a session from Supabase."""
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT messages FROM chat_messages WHERE user_id = %s AND thread_id = %s;",
                (user_id, thread_id)
            )
            row = cur.fetchone()
            if row:
                serialized = row[0]
                if isinstance(serialized, str):
                    serialized = json.loads(serialized)
                return messages_from_dict(serialized)
    except Exception as e:
        logger.error(f"Failed to load messages from Supabase: {e}", exc_info=True)
    return []


def append_new_messages_to_db(user_id: str, thread_id: str, new_messages: list):
    """
    Append only genuinely new messages from this turn into PostgreSQL.
    """
    save_messages_to_postgress(user_id, thread_id, new_messages)


def get_langfuse_callback(user_id: str, thread_id: str):
    """
    Instantiates and returns the Langfuse CallbackHandler if API keys are set.
    """
    if settings.LANGFUSE_SECRET_KEY and settings.LANGFUSE_PUBLIC_KEY:
        try:
            from langfuse import Langfuse
            from langfuse.langchain import CallbackHandler
            
            # Instantiate Langfuse client to register it under the public key in the global registry
            _ = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_BASE_URL or "https://cloud.langfuse.com"
            )
            
            return CallbackHandler(public_key=settings.LANGFUSE_PUBLIC_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse callback: {e}", exc_info=True)
    return None


class QueueCallbackHandler(BaseCallbackHandler):
    def __init__(self, q: queue.Queue):
        self.q = q
        self.active_stream = False

    def on_llm_start(self, serialized, prompts, **kwargs):
        metadata = kwargs.get("metadata", {})
        node = metadata.get("langgraph_node", "")
        # Filter out planner node's LLM tokens (JSON structured data)
        if node == "planner":
            self.active_stream = False
            self.q.put({"type": "status", "content": "Analyzing request intent..."})
        else:
            self.active_stream = True
            checkpoint_ns = metadata.get("checkpoint_ns", "")
            agent_name = checkpoint_ns.split(":")[0].replace("_node", "").replace("_", " ").title() if checkpoint_ns else "assistant"
            self.q.put({"type": "status", "content": f"Cinemagic {agent_name} formulating response..."})

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        if self.active_stream:
            self.q.put({"type": "token", "content": token})

    def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = serialized.get("name", "")
        nice_name = tool_name.replace("_", " ").title()
        self.q.put({"type": "status", "content": f"Retrieving database records ({nice_name})..."})


def run_graph_in_thread(inputs, config, q: queue.Queue, resume_value: str | None = None):
    """Runner function executed inside uvicorn's thread pool to invoke the StateGraph."""
    try:
        # Get existing state messages before invoking to isolate newly generated messages
        pre_snapshot = graph.get_state(config)
        old_messages = pre_snapshot.values.get("messages", [])
        old_ids = {getattr(m, "id", None) for m in old_messages if getattr(m, "id", None)}

        if resume_value is not None:
            graph.invoke(Command(resume=resume_value, update=inputs), config)
        else:
            graph.invoke(inputs, config)
            
        snapshot = graph.get_state(config)
        interrupt_info = get_active_interrupt(snapshot)
        logger.info(f"[HITL-DEBUG] graph finished. interrupt_info={'present: ' + str(interrupt_info.get('message')) if interrupt_info else 'None'}")
        
        all_messages = snapshot.values.get("messages", [])
        
        # Filter only genuinely new messages generated/received during this execution turn
        new_messages = [m for m in all_messages if getattr(m, "id", None) not in old_ids]
        
        # Append only genuinely new messages to PostgreSQL, never overwrite full history
        append_new_messages_to_db(inputs["user_id"], inputs["thread_id"], new_messages)
        
        # Always load the complete history from DB as the source of truth
        full_messages = load_messages_from_postgress(inputs["user_id"], inputs["thread_id"])
        formatted_msgs = format_messages(full_messages)
        
        status = "requires_confirmation" if interrupt_info else "success"
        complete_event = {
            "type": "complete",
            "status": status,
            "messages": formatted_msgs
        }
        if interrupt_info:
            complete_event["interrupt"] = interrupt_info
            
        q.put(complete_event)
    except Exception as e:
        logger.error(f"Error in graph execution thread: {str(e)}", exc_info=True)
        q.put({"type": "error", "message": f"Graph execution failed: {str(e)}"})
    finally:
        q.put(None)
