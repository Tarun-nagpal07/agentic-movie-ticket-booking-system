import json
import logging
import queue
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, messages_to_dict, messages_from_dict
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.types import Command
from src.graph.graph import get_graph
from src.utils.logger import get_logger
from src.db.postgres import init_db, get_db_cursor
from src.utils.rate_limiter import RateLimiter

# Initialize logger
logger = get_logger("fastapi_app")

app = FastAPI(title="Movie Ticket Booking Chat API")

# Initialize parent LangGraph compiled graph
graph = get_graph()

# Initialize Database Schema & Auto-seed preferences if empty
init_db()


class ChatRequest(BaseModel):
    user_id: str
    thread_id: str
    message: str


class ConfirmRequest(BaseModel):
    user_id: str
    thread_id: str
    decision: str  # "Approve" or "Reject"


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception in {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "error": str(exc)},
    )


@app.get("/")
def home():
    return {"message": "Movie Booking Assistant Chat API is running."}


@app.get("/movies", dependencies=[Depends(RateLimiter(limit=20, window=60, scope="movies"))])
def get_movies():
    try:
        with open("data/movies.json", "r", encoding="utf-8") as file:
            movies = json.load(file)
        return movies
    except Exception as e:
        logger.error(f"Failed to read movies.json: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load movies data."
        )


def format_messages(messages):
    formatted = []
    for m in messages:
        # Determine role
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
    if snapshot.tasks:
        for task in snapshot.tasks:
            if task.interrupts:
                return task.interrupts[0].value
    return None


def save_messages_to_postgress(user_id: str, thread_id: str, messages: list):
    """Serialize and save/upsert the entire chat history for a session to Supabase."""
    try:
        serialized_messages = messages_to_dict(messages)
        with get_db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_messages (user_id, thread_id, messages, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, thread_id) DO UPDATE
                SET messages = EXCLUDED.messages, updated_at = CURRENT_TIMESTAMP;
                """,
                (user_id, thread_id, json.dumps(serialized_messages))
            )
        logger.info(f"Saved {len(messages)} messages to Supabase for user={user_id}, thread={thread_id}")
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


def append_new_messages_to_db(user_id: str, thread_id: str, graph_state_messages: list):
    """
    Append only genuinely new messages from this turn into PostgreSQL.

    PostgreSQL is the single source of truth for the full history.
    The graph state may be trimmed to 15 messages by middleware, so we NEVER
    overwrite the DB with the graph state. Instead we identify which message IDs
    are not yet in the DB and append only those.
    """
    try:
        db_messages = load_messages_from_postgress(user_id, thread_id)

        # Build set of IDs already persisted
        db_ids = {getattr(m, "id", None) for m in db_messages if getattr(m, "id", None)}

        # Collect only new messages (not yet in DB)
        new_msgs = [m for m in graph_state_messages if getattr(m, "id", None) not in db_ids]

        if not new_msgs:
            logger.info(f"No new messages to append for user={user_id}, thread={thread_id}")
            return

        merged = db_messages + new_msgs
        save_messages_to_postgress(user_id, thread_id, merged)
        logger.info(f"Appended {len(new_msgs)} new message(s) to DB for user={user_id}, thread={thread_id} (total={len(merged)})")
    except Exception as e:
        logger.error(f"Failed to append new messages to DB: {e}", exc_info=True)


def get_langfuse_callback(user_id: str, thread_id: str):
    """
    Instantiates and returns the Langfuse CallbackHandler if API keys are set.
    """
    try:
        from src.config.settings import settings
    except ImportError:
        logger.error("Could not import settings from src.config.settings")
        return None

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
            
            # Instantiate CallbackHandler using the public key
            return CallbackHandler(
                public_key=settings.LANGFUSE_PUBLIC_KEY
            )
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


def run_graph_in_thread(inputs, config, q: queue.Queue):
    try:
        graph.invoke(inputs, config)
        snapshot = graph.get_state(config)
        interrupt_info = get_active_interrupt(snapshot)
        all_messages = snapshot.values.get("messages", [])
        
        # Append only genuinely new messages to PostgreSQL, never overwrite full history
        append_new_messages_to_db(inputs["user_id"], inputs["thread_id"], all_messages)
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


@app.post("/chat/stream", dependencies=[Depends(RateLimiter(limit=5, window=10, scope="chat"))])
async def chat_stream_endpoint(request: ChatRequest):
    try:
        logger.info(f"Chat stream request received: user={request.user_id}, thread={request.thread_id}, msg='{request.message[:40]}'")
        
        config = {
            "configurable": {
                "thread_id": request.thread_id,
                "user_id": request.user_id
            },
            "metadata": {
                "langfuse_user_id": request.user_id,
                "langfuse_session_id": request.thread_id
            }
        }
        
        # Check if Redis checkpointer has existing state
        if not graph.get_state(config).values.get("messages"):
            logger.info(f"Redis cache miss for thread {request.thread_id} — loading chat history from Supabase")
            db_messages = load_messages_from_postgress(request.user_id, request.thread_id)
            if db_messages:
                graph.update_state(config, {
                    "messages": db_messages,
                    "user_id": request.user_id,
                    "thread_id": request.thread_id
                })
                logger.info(f"Rehydrated thread {request.thread_id} with {len(db_messages)} messages from Supabase")
                
        inputs = {
            "messages": [HumanMessage(content=request.message)],
            "user_id": request.user_id,
            "thread_id": request.thread_id
        }
        
        # Create queue and handler
        q = queue.Queue()
        q.put({"type": "status", "content": "Initializing Cinemagic graph..."})
        callbacks = [QueueCallbackHandler(q)]
        langfuse_cb = get_langfuse_callback(request.user_id, request.thread_id)
        if langfuse_cb:
            callbacks.append(langfuse_cb)
        config["callbacks"] = callbacks
        
        # Run graph in thread pool executor
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, run_graph_in_thread, inputs, config, q)
        
        async def event_generator():
            while True:
                # Read from queue in a non-blocking thread pool worker
                event = await asyncio.to_thread(q.get)
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
                
        return StreamingResponse(event_generator(), media_type="text/event-stream")
        
    except Exception as e:
        logger.error(f"Error initializing chat stream: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize chat stream: {str(e)}"
        )


@app.post("/chat", dependencies=[Depends(RateLimiter(limit=5, window=10, scope="chat"))])
async def chat_endpoint(request: ChatRequest):
    try:
        logger.info(f"Chat request received: user={request.user_id}, thread={request.thread_id}, msg='{request.message[:40]}'")

        config = {
            "configurable": {
                "thread_id": request.thread_id,
                "user_id": request.user_id
            },
            "metadata": {
                "langfuse_user_id": request.user_id,
                "langfuse_session_id": request.thread_id
            }
        }

        # Check if Redis checkpointer has existing state
        snapshot = graph.get_state(config)
        if not snapshot.values.get("messages"):
            # Redis cache miss — rehydrate from postgress if we have history
            logger.info(f"Redis cache miss for thread {request.thread_id} — loading chat history from Supabase")
            db_messages = load_messages_from_postgress(request.user_id, request.thread_id)
            if db_messages:
                graph.update_state(config, {
                    "messages": db_messages,
                    "user_id": request.user_id,
                    "thread_id": request.thread_id
                })
                logger.info(f"Rehydrated thread {request.thread_id} with {len(db_messages)} messages from Supabase")

        # Add Langfuse callback handler if available
        langfuse_cb = get_langfuse_callback(request.user_id, request.thread_id)
        if langfuse_cb:
            config["callbacks"] = [langfuse_cb]

        # Invoke the graph with user_id and the new user message
        graph.invoke(
            {
                "messages": [HumanMessage(content=request.message)],
                "user_id": request.user_id,
                "thread_id": request.thread_id
            },
            config
        )

        # Retrieve current snapshot after invocation (either completed or paused on interrupt)
        snapshot = graph.get_state(config)
        interrupt_info = get_active_interrupt(snapshot)

        all_messages = snapshot.values.get("messages", [])
        
        # Append only genuinely new messages to PostgreSQL, never overwrite full history
        append_new_messages_to_db(request.user_id, request.thread_id, all_messages)
        # Always load the complete history from DB as the source of truth
        full_messages = load_messages_from_postgress(request.user_id, request.thread_id)
        formatted_msgs = format_messages(full_messages)

        if interrupt_info:
            logger.info(f"Graph paused at interrupt: {interrupt_info.get('message')}")
            return {
                "status": "requires_confirmation",
                "interrupt": interrupt_info,
                "messages": formatted_msgs
            }

        logger.info("Graph execution completed successfully")
        return {
            "status": "success",
            "messages": formatted_msgs
        }

    except Exception as e:
        logger.error(f"Error during chat processing: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing chat turn: {str(e)}"
        )


@app.get("/chat/threads", dependencies=[Depends(RateLimiter(limit=20, window=10, scope="threads"))])
def get_chat_threads(user_id: str):
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT thread_id FROM chat_messages WHERE user_id = %s ORDER BY updated_at DESC;",
                (user_id,)
            )
            rows = cur.fetchall()
            threads = [row[0] for row in rows]
            return {"threads": threads}
    except Exception as e:
        logger.error(f"Error fetching threads: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching threads: {str(e)}"
        )


@app.get("/chat/history", dependencies=[Depends(RateLimiter(limit=10, window=10, scope="history"))])
def get_chat_history(user_id: str, thread_id: str):
    try:
        # ALWAYS fetch full history from PostgreSQL, not from trimmed state
        # Middleware trims state for model input, but we must show complete history to frontend
        db_messages = load_messages_from_postgress(user_id, thread_id)
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id
            }
        }
        snapshot = graph.get_state(config)
        interrupt_info = get_active_interrupt(snapshot)

        formatted_msgs = format_messages(db_messages) if db_messages else []
        logger.info(f"Returning {len(formatted_msgs)} messages from PostgreSQL for user={user_id}, thread={thread_id}")
        
        return {
            "status": "requires_confirmation" if interrupt_info else "success",
            "interrupt": interrupt_info,
            "messages": formatted_msgs
        }
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching history: {str(e)}"
        )


@app.delete("/chat/threads", dependencies=[Depends(RateLimiter(limit=20, window=10, scope="threads"))])
def delete_chat_thread(user_id: str, thread_id: str):
    try:
        # 1. Delete from PostgreSQL
        with get_db_cursor() as cur:
            cur.execute(
                "DELETE FROM chat_messages WHERE user_id = %s AND thread_id = %s;",
                (user_id, thread_id)
            )
        logger.info(f"Deleted thread {thread_id} messages for user {user_id} from PostgreSQL")

        # 2. Delete checkpointer keys from Redis
        try:
            import redis
            from src.config.settings import settings
            r = redis.Redis.from_url(settings.REDIS_URL)
            patterns = [
                f"checkpoint:{thread_id}:*",
                f"checkpoint_write:{thread_id}:*",
                f"write_keys_zset:{thread_id}:*"
            ]
            deleted_keys_count = 0
            for pattern in patterns:
                keys = r.keys(pattern)
                if keys:
                    r.delete(*keys)
                    deleted_keys_count += len(keys)
            logger.info(f"Cleared {deleted_keys_count} Redis checkpointer keys for thread {thread_id}")
        except Exception as re_err:
            logger.error(f"Failed to clear Redis checkpoints for thread {thread_id}: {re_err}")

        return {"status": "success", "message": f"Thread {thread_id} deleted successfully."}
    except Exception as e:
        logger.error(f"Error deleting thread {thread_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting thread: {str(e)}"
        )


@app.put("/chat/threads", dependencies=[Depends(RateLimiter(limit=20, window=10, scope="threads"))])
def rename_chat_thread(user_id: str, old_thread_id: str, new_thread_id: str):
    if not new_thread_id or not new_thread_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New thread ID cannot be empty."
        )
    try:
        # 1. Update in PostgreSQL
        with get_db_cursor() as cur:
            # Check if new thread ID already exists to avoid conflict
            cur.execute(
                "SELECT 1 FROM chat_messages WHERE user_id = %s AND thread_id = %s;",
                (user_id, new_thread_id)
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A thread named '{new_thread_id}' already exists."
                )

            cur.execute(
                """
                UPDATE chat_messages 
                SET thread_id = %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND thread_id = %s;
                """,
                (new_thread_id, user_id, old_thread_id)
            )
        logger.info(f"Renamed thread {old_thread_id} to {new_thread_id} for user {user_id} in PostgreSQL")

        # 2. Delete checkpointer keys for both old and new threads from Redis to be completely clean
        # (when the new thread is accessed next, it will rehydrate from PostgreSQL)
        try:
            import redis
            from src.config.settings import settings
            r = redis.Redis.from_url(settings.REDIS_URL)
            for tid in [old_thread_id, new_thread_id]:
                patterns = [
                    f"checkpoint:{tid}:*",
                    f"checkpoint_write:{tid}:*",
                    f"write_keys_zset:{tid}:*"
                ]
                deleted_keys_count = 0
                for pattern in patterns:
                    keys = r.keys(pattern)
                    if keys:
                        r.delete(*keys)
                        deleted_keys_count += len(keys)
                logger.info(f"Cleared {deleted_keys_count} Redis checkpointer keys for thread {tid}")
        except Exception as re_err:
            logger.error(f"Failed to clear Redis checkpoints during rename: {re_err}")

        return {"status": "success", "message": f"Thread {old_thread_id} renamed to {new_thread_id} successfully."}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error renaming thread {old_thread_id} to {new_thread_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error renaming thread: {str(e)}"
        )


@app.post("/chat/confirm", dependencies=[Depends(RateLimiter(limit=5, window=10, scope="confirm"))])
async def confirm_endpoint(request: ConfirmRequest):
    try:
        logger.info(f"Confirm request received: user={request.user_id}, thread={request.thread_id}, decision={request.decision}")

        config = {
            "configurable": {
                "thread_id": request.thread_id,
                "user_id": request.user_id
            },
            "metadata": {
                "langfuse_user_id": request.user_id,
                "langfuse_session_id": request.thread_id
            }
        }

        # Check if Redis checkpointer has existing state
        snapshot = graph.get_state(config)
        if not snapshot.values.get("messages"):
            # Redis cache miss — rehydrate from Postgress if we have history
            logger.info(f"Redis cache miss on confirm for thread {request.thread_id} — loading chat history from Supabase")
            db_messages = load_messages_from_postgress(request.user_id, request.thread_id)
            if db_messages:
                graph.update_state(config, {
                    "messages": db_messages,
                    "user_id": request.user_id,
                    "thread_id": request.thread_id
                })
                logger.info(f"Rehydrated thread {request.thread_id} on confirm from Supabase")
                snapshot = graph.get_state(config)

        interrupt_info = get_active_interrupt(snapshot)

        if not interrupt_info:
            logger.warning("No active interrupt found to confirm")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="There is no active confirmation pending for this conversation thread."
            )

        if request.decision not in ["Approve", "Reject"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Decision must be either 'Approve' or 'Reject'."
            )

        # Add Langfuse callback handler if available
        langfuse_cb = get_langfuse_callback(request.user_id, request.thread_id)
        if langfuse_cb:
            config["callbacks"] = [langfuse_cb]

        # Resume graph execution with the decision
        graph.invoke(Command(resume=request.decision), config)

        # Retrieve updated snapshot after resumption
        new_snapshot = graph.get_state(config)
        new_interrupt_info = get_active_interrupt(new_snapshot)

        all_messages = new_snapshot.values.get("messages", [])
        
        # Append only genuinely new messages to PostgreSQL, never overwrite full history
        append_new_messages_to_db(request.user_id, request.thread_id, all_messages)
        # Always load the complete history from DB as the source of truth
        full_messages = load_messages_from_postgress(request.user_id, request.thread_id)
        formatted_msgs = format_messages(full_messages)

        if new_interrupt_info:
            logger.info(f"Graph paused at subsequent interrupt: {new_interrupt_info.get('message')}")
            return {
                "status": "requires_confirmation",
                "interrupt": new_interrupt_info,
                "messages": formatted_msgs
            }

        logger.info("Graph execution completed successfully after confirmation")
        return {
            "status": "success",
            "messages": formatted_msgs
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error during confirmation processing: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing confirmation turn: {str(e)}"
        )
