import json
import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, messages_to_dict, messages_from_dict
from langgraph.types import Command
from src.graph.graph import get_graph
from src.utils.logger import get_logger
from src.db.postgres import init_db, get_db_cursor

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


@app.get("/movies")
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


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        logger.info(f"Chat request received: user={request.user_id}, thread={request.thread_id}, msg='{request.message[:40]}'")

        config = {
            "configurable": {
                "thread_id": request.thread_id,
                "user_id": request.user_id
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
        formatted_msgs = format_messages(all_messages)

        # Persist updated message history to postgress
        save_messages_to_postgress(request.user_id, request.thread_id, all_messages)

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


@app.get("/chat/history")
def get_chat_history(user_id: str, thread_id: str):
    try:
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id
            }
        }
        snapshot = graph.get_state(config)

        # Rehydrate from postgress if Redis cache has expired or is empty
        if not snapshot.values.get("messages"):
            logger.info(f"Redis cache miss for thread {thread_id} history request — fetching from Supabase")
            db_messages = load_messages_from_postgress(user_id, thread_id)
            if db_messages:
                graph.update_state(config, {
                    "messages": db_messages,
                    "user_id": user_id,
                    "thread_id": thread_id
                })
                logger.info(f"Rehydrated thread {thread_id} in checkpointer from Supabase")
                snapshot = graph.get_state(config)

        formatted_msgs = format_messages(snapshot.values.get("messages", []))
        interrupt_info = get_active_interrupt(snapshot)
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


@app.post("/chat/confirm")
async def confirm_endpoint(request: ConfirmRequest):
    try:
        logger.info(f"Confirm request received: user={request.user_id}, thread={request.thread_id}, decision={request.decision}")

        config = {
            "configurable": {
                "thread_id": request.thread_id,
                "user_id": request.user_id
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

        # Resume graph execution with the decision
        graph.invoke(Command(resume=request.decision), config)

        # Retrieve updated snapshot after resumption
        new_snapshot = graph.get_state(config)
        new_interrupt_info = get_active_interrupt(new_snapshot)

        all_messages = new_snapshot.values.get("messages", [])
        formatted_msgs = format_messages(all_messages)

        # Persist updated message history to postgress
        save_messages_to_postgress(request.user_id, request.thread_id, all_messages)

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
