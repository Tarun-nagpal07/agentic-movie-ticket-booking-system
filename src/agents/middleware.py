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
    and the last 15 messages of conversation history, and strip large metadata.
    """
    messages = state.get("messages", [])
    print(f"--- MIDDLEWARE TRIGGERED --- Messages count: {len(messages)}")
    
    if not messages:
        return None

    # Strip seat_maps from all messages to prevent prompt context bloat
    cleaned_messages = []
    modified = False
    for msg in messages:
        if getattr(msg, "additional_kwargs", None) and "seat_maps" in msg.additional_kwargs:
            if hasattr(msg, "model_copy"):
                msg_copy = msg.model_copy()
            else:
                msg_copy = msg.copy()
            msg_copy.additional_kwargs = msg.additional_kwargs.copy()
            msg_copy.additional_kwargs.pop("seat_maps", None)
            cleaned_messages.append(msg_copy)
            modified = True
        else:
            cleaned_messages.append(msg)

    # Trim if we exceed 16 messages (1 system prompt + 15 conversation messages)
    if len(cleaned_messages) > 16:
        system_msg = cleaned_messages[0]
        recent_messages = cleaned_messages[-15:]
        final_messages = [system_msg] + recent_messages
        logger.info(f"trim_messages middleware: Pruning conversation messages from {len(messages)} to {len(final_messages)} messages.")
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *final_messages
            ]
        }
    
    if modified:
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *cleaned_messages
            ]
        }
        
    return None


def extract_new_messages(input_messages: list[Any], output_messages: list[Any]) -> list[Any]:
    """
    Extracts only the new messages from output_messages that were added
    after input_messages. Handles the case where output_messages was trimmed
    by the trim_messages middleware.
    """
    if not input_messages:
        return output_messages

    # We search output_messages to find the position of the last input message.
    # The last input message (input_messages[-1]) is the user's query (HumanMessage).
    # Since trimming keeps the last 15 messages, input_messages[-1] is guaranteed
    # to be in the trimmed output_messages.
    last_input_msg = input_messages[-1]
    
    match_idx = -1
    for idx in range(len(output_messages) - 1, -1, -1):
        msg = output_messages[idx]
        # 1. Object identity
        if msg is last_input_msg:
            match_idx = idx
            break
        # 2. Match by id if available
        if (getattr(msg, "id", None) is not None and 
            getattr(last_input_msg, "id", None) is not None and 
            msg.id == last_input_msg.id):
            match_idx = idx
            break
        # 3. Match by type and content
        if (getattr(msg, "type", None) == getattr(last_input_msg, "type", None) and 
            getattr(msg, "content", None) == getattr(last_input_msg, "content", None)):
            match_idx = idx
            break

    if match_idx != -1:
        # The new messages are everything after the matched last input message
        return output_messages[match_idx + 1:]
    
    # Fallback slicing:
    if len(output_messages) < len(input_messages):
        # Trimmed: system message + 15 recent messages = 16 messages.
        return output_messages[16:]
    else:
        # Untrimmed
        return output_messages[len(input_messages):]

