from typing import Any
from langchain.agents.middleware import before_model
from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from src.utils.logger import get_logger

logger = get_logger(__name__)

@before_model
def trim_messages(state: dict[str, Any], runtime: Any) -> dict[str, Any] | None:
    """
    LangChain/LangGraph agent middleware to keep only the first message (system prompt)
    and the last 15 messages of conversation history.
    """
    messages = state.get("messages", [])
    print(f"--- MIDDLEWARE TRIGGERED --- Messages count: {len(messages)}")
    
    if not messages:
        return None

    # Trim only if we exceed 16 messages (1 system prompt + 15 conversation messages)
    if len(messages) <= 16:
        return None

    system_msg = messages[0]
    recent_messages = messages[-15:]
    new_messages = [system_msg] + recent_messages

    logger.info(f"trim_messages middleware: Pruning conversation messages from {len(messages)} to {len(new_messages)} messages.")
    
    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *new_messages
        ]
    }
