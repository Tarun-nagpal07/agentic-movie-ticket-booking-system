from src.utils.logger import get_logger
from src.agents.llm import get_llm
from src.prompts.confirmation import CLASSIFY_CONFIRMATION_PROMPT

logger = get_logger(__name__)

def classify_confirmation_input(user_input: str) -> str:
    """
    Classifies the user's input during a booking/cancellation confirmation step.
    Returns: "Approve", "Reject", or "Query".
    """
    if not user_input:
        return "Query"

    cleaned = user_input.strip().lower().rstrip(".!?")
    
    # Exact/simple matches first
    if cleaned in (
        "approve", "yes", "yess", "y", "confirm", "go ahead", "proceed", 
        "ok", "okay", "sure", "yep", "yeah", "yesss", "correct", "yup", "yessss"
    ):
        return "Approve"
    if cleaned in (
        "reject", "no", "n", "cancel", "cancel it", "stop", "dont", "don't", 
        "no thanks", "nope", "decline", "nay"
    ):
        return "Reject"
        
    # Use LLM for conversational matching
    llm = get_llm()
    prompt = CLASSIFY_CONFIRMATION_PROMPT.format(user_input=user_input)
    try:
        response = llm.invoke(prompt)
        result = response.content.strip().replace('"', '').replace('.', '')
        if result in ("Approve", "Reject", "Query"):
            logger.info(f"LLM classified confirmation input '{user_input}' as '{result}'")
            return result
        else:
            logger.warning(f"LLM returned unexpected confirmation classification: '{result}' for input '{user_input}'")
    except Exception as e:
        logger.error(f"Error classifying confirmation input '{user_input}': {e}", exc_info=True)
    
    return "Query"
