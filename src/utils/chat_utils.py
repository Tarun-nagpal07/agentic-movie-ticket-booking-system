import json
import re
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, messages_to_dict, messages_from_dict
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from src.graph.graph import get_graph
from src.utils.logger import get_logger
from src.db.postgres import get_db_cursor
from src.config.settings import settings
from src.api import services


logger = get_logger("chat_utils")

# Lazily initialized async graph instance
_graph = None


async def get_graph_instance():
    """Lazily initialize and cache the async-compiled LangGraph instance."""
    global _graph
    if _graph is None:
        _graph = await get_graph()
    return _graph


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

        msg_dict = {
            "role": role,
            "content": getattr(m, "content", str(m))
        }
        if m.type == "ai" and hasattr(m, "additional_kwargs"):
            if "movie_posters" in m.additional_kwargs:
                msg_dict["movie_posters"] = m.additional_kwargs["movie_posters"]
            if "seat_maps" in m.additional_kwargs:
                msg_dict["seat_maps"] = m.additional_kwargs["seat_maps"]
        formatted.append(msg_dict)
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
        for msg_dict in serialized_messages:
            if msg_dict.get("type") == "ai":
                data = msg_dict.setdefault("data", {})
                content = data.get("content", "")
                if content:
                    show_ids = re.findall(r"\[SEAT_MAP:([a-zA-Z0-9_]+)(?::[a-zA-Z0-9_,]+)?\]", content)
                    if show_ids:
                        additional_kwargs = data.setdefault("additional_kwargs", {})
                        seat_maps = additional_kwargs.setdefault("seat_maps", {})
                        for show_id in show_ids:
                            if show_id not in seat_maps:
                                show = services.get_show_details(show_id)
                                if show:
                                    seats_dict = services.get_show_seats(show_id)
                                    seat_maps[show_id] = {
                                        "seats": seats_dict,
                                        "seat_types": show.get("seat_types", {})
                                    }
                                    logger.info(f"Snapshotted seats for show_id={show_id} in serialized assistant message")
                                else:
                                    logger.warning(f"Could not fetch show details for show_id={show_id} during snapshotting")

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


def log_token_usage(new_messages: list, endpoint: str, user_id: str, thread_id: str):
    """
    Extracts and logs token usage from AI messages generated during this turn.
    Each AIMessage may carry usage_metadata with input_tokens, output_tokens, total_tokens.
    """
    total_input = 0
    total_output = 0
    total_tokens = 0
    llm_calls = 0

    for m in new_messages:
        usage = getattr(m, "usage_metadata", None)
        if usage and isinstance(usage, dict):
            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)
            total_tokens += usage.get("total_tokens", 0)
            llm_calls += 1

    if llm_calls > 0:
        logger.info(
            f"[TOKEN USAGE] endpoint={endpoint} | user={user_id} | thread={thread_id} | "
            f"llm_calls={llm_calls} | input_tokens={total_input} | "
            f"output_tokens={total_output} | total_tokens={total_tokens}"
        )
    else:
        logger.info(
            f"[TOKEN USAGE] endpoint={endpoint} | user={user_id} | thread={thread_id} | "
            f"no token usage metadata available"
        )
