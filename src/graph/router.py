from src.graph.state import BookingState
from src.utils.logger import get_logger

logger = get_logger(__name__)

def route_agent(state: BookingState) -> str:
    """
    Conditional routing edge.
    Reads `next_agent` from state and determines the next node to execute.
    """
    next_agent = state.get("next_agent")

    logger.info(f"router.py: routing based on next_agent='{next_agent}'")

    if next_agent == "booking":
        return "booking_node"
    elif next_agent == "seat":
        return "seat_node"
    elif next_agent == "recommend":
        return "recommendation_node"
    elif next_agent == "cancellation":
        return "cancellation_node"
    elif next_agent == "history":
        return "history_node"
    elif next_agent == "policy":
        return "policy_node"
    elif next_agent == "unknown":
        return "unknown"
    else:
        logger.warning(f"router.py: unmapped next_agent '{next_agent}' — routing to unknown")
        return "unknown"
