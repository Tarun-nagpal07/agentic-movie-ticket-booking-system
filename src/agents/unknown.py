from langchain_core.messages import AIMessage
from src.agents.llm import get_llm
from src.graph.state import BookingState
from src.prompts.unknown import REFUSAL_PROMPT_TEMPLATE
from src.utils.logger import get_logger

logger = get_logger(__name__)


def unknown_node(state: BookingState) -> dict:
    """
    Node executed when the user's intent is unknown or not mapped.
    Generates a professional, polite refusal response.
    """
    logger.info("Executing unknown_node for unmapped intent.")
    
    messages = state.get("messages", [])
    
    # Extract the last human message content for context
    user_message_content = ""
    for m in reversed(messages):
        if getattr(m, "type", None) == "human":
            user_message_content = getattr(m, "content", "")
            break

    refusal_prompt = REFUSAL_PROMPT_TEMPLATE.format(user_message_content=user_message_content)
    llm_streaming = get_llm(structure=False)
    refusal_response = llm_streaming.invoke(
        [{"role": "system", "content": refusal_prompt}],
        config={"tags": ["refusal_response"]}
    )
    
    return {
        "messages": [AIMessage(content=refusal_response.content)]
    }
