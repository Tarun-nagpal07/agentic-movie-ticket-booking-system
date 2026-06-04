import json
import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from src.graph.graph import get_graph
from src.utils.logger import get_logger

# Initialize logger
logger = get_logger("fastapi_app")

app = FastAPI(title="Movie Ticket Booking Chat API")

# Initialize parent LangGraph compiled graph
graph = get_graph()


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

        formatted_msgs = format_messages(snapshot.values.get("messages", []))

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

        formatted_msgs = format_messages(new_snapshot.values.get("messages", []))

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
