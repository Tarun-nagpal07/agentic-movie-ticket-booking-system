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
    and the last 10 messages of conversation history, strip large metadata,
    and dynamically truncate large intermediate payloads to prevent context limits.
    """
    messages = state.get("messages", [])
    
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

    # Calculate total character length of the messages context (roughly 4 chars = 1 token)
    total_len = sum(len(getattr(m, "content", "")) for m in cleaned_messages if isinstance(getattr(m, "content", None), str))
    
    # If context exceeds ~6,000 tokens (24,000 characters), truncate large intermediate tool/assistant payloads
    if total_len > 24000:
        logger.warning(f"trim_messages middleware: Context size ({total_len} chars) is large. Truncating large payloads...")
        # Keep system prompt (cleaned_messages[0]) and user's latest query (cleaned_messages[-1]) intact.
        # Truncate intermediate messages if their text is very large.
        for idx in range(1, len(cleaned_messages) - 1):
            msg = cleaned_messages[idx]
            content = getattr(msg, "content", "")
            if isinstance(content, str) and len(content) > 1500:
                if hasattr(msg, "model_copy"):
                    msg_copy = msg.model_copy()
                else:
                    msg_copy = msg.copy()
                msg_copy.content = content[:500] + "\n\n[... Large output truncated to conserve context space ...]"
                cleaned_messages[idx] = msg_copy
                modified = True
                
        # Re-evaluate total length; if still too large, aggressively slice to last 5 messages
        total_len = sum(len(getattr(m, "content", "")) for m in cleaned_messages if isinstance(getattr(m, "content", None), str))
        if total_len > 24000:
            logger.warning(f"trim_messages middleware: Context still too large ({total_len} chars). Aggressively pruning to 5 messages limit.")
            system_msg = cleaned_messages[0]
            recent_messages = cleaned_messages[-5:]
            cleaned_messages = [system_msg] + recent_messages
            modified = True

    # Crop to 10 conversation messages limit (1 system prompt + 10 recent messages = 11 messages)
    if len(cleaned_messages) > 11:
        system_msg = cleaned_messages[0]
        recent_messages = cleaned_messages[-10:]
        cleaned_messages = [system_msg] + recent_messages
        modified = True
        logger.info(f"trim_messages middleware: Pruning conversation messages to 10 messages limit (total 11).")
    
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

    last_input_msg = input_messages[-1]
    
    match_idx = -1
    for idx in range(len(output_messages) - 1, -1, -1):
        msg = output_messages[idx]
        if msg is last_input_msg:
            match_idx = idx
            break
        if (getattr(msg, "id", None) is not None and 
            getattr(last_input_msg, "id", None) is not None and 
            msg.id == last_input_msg.id):
            match_idx = idx
            break
        if (getattr(msg, "type", None) == getattr(last_input_msg, "type", None) and 
            getattr(msg, "content", None) == getattr(last_input_msg, "content", None)):
            match_idx = idx
            break

    if match_idx != -1:
        return output_messages[match_idx + 1:]
    
    # Fallback slicing:
    # Trimmed: system message + 10 recent messages = 11 messages.
    if len(output_messages) < len(input_messages):
        return output_messages[11:]
    else:
        return output_messages[len(input_messages):]
