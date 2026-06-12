from src.utils.logger import get_logger

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
    from src.agents.llm import get_llm
    llm = get_llm()
    prompt = f"""You are an assistant determining the user's intent on a confirmation screen.
The user is presented with a booking confirmation and is asked to Approve or Reject it.
The user's response is: "{user_input}"

Classify their response into exactly one of these categories:
- Approve: if they are agreeing, saying yes, confirming, or telling the assistant to go ahead.
- Reject: if they are saying no, rejecting, canceling, or telling the assistant to stop.
- Query: if they are asking a question, trying to change booking details (like number of tickets, seat type, date, movie, showtime), or speaking about something else.

Respond with ONLY one of the words: "Approve", "Reject", or "Query". Do not include punctuation or other text.
"""
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
