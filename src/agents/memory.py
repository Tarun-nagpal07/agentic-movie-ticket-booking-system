from src.graph.state import MemoryAgentState, BookingState
from src.memory.long_term import get_user_memory, update_user_memory
from src.utils.logger import get_logger

logger = get_logger(__name__)

def memory_read_node(state: BookingState) -> dict:
    """
    Runs at graph START on every turn.

    Optimization — skip expensive reads after the first turn:
    - LangGraph's checkpointer already persists the BookingState (including `memory`) between turns.
    - Only do the full load when the session is fresh (memory not yet in state).
    """
    user_id  = state["user_id"]
    updates = {}

    # Reset confirmation / redirect flags and finished drafts
    if state.get("confirmed") is not None:
        updates["confirmed"] = None
    if state.get("redirect_to_planner"):
        updates["redirect_to_planner"] = None

    booking_draft = state.get("booking_draft")
    if booking_draft and booking_draft.get("status") == "confirmed":
        updates["booking_draft"] = None

    cancel_draft = state.get("cancel_draft")
    if cancel_draft and cancel_draft.get("status") == "cancelled":
        updates["cancel_draft"] = None

    # Already loaded from a previous turn's checkpoint — skip
    if state.get("memory"):
        logger.info(f"memory_read: state already has memory for user {user_id} — skipping load and returning resets")
        return updates

    # Fresh session — load from PostgreSQL (long-term store)
    logger.info(f"memory_read: fresh session for user {user_id} — loading from PostgreSQL")
    user_memory = get_user_memory(user_id)

    logger.info(f"memory_read complete for user {user_id}: loaded memory")
    updates["memory"] = user_memory or {}
    return updates


def memory_write_node(state: MemoryAgentState) -> MemoryAgentState:
    """
    Runs at graph END.

    Persists user preferences back to database when booking or cancellation occurs.
    """
    user_id   = state["user_id"]
    confirmed = state.get("confirmed")
    updates   = {}

    # booking confirmed
    if confirmed and state.get("booking_draft"):
        draft = state["booking_draft"]

        updates["preferred_theaters"] = [draft["theater_id"]]

        # infer seat type from booked seats using seat_types map
        if draft.get("seats") and draft.get("seat_types"):
            row       = draft["seats"][0][0]      # e.g. "E" from "E5"
            seat_type = draft["seat_types"].get(row)
            if seat_type:
                updates["preferred_seat_type"] = seat_type

        # infer format preference
        if draft.get("format"):
            updates["preferred_format"] = draft["format"]

        logger.info(f"memory_write: booking {draft['booking_id']} confirmed for user {user_id}")

    # cancellation confirmed
    if state.get("cancel_draft"):
        draft = state["cancel_draft"]
        if draft.get("status") == "cancelled":
            logger.info(f"memory_write: cancellation {draft['booking_id']} recorded for user {user_id}")

    # nothing meaningful happened — skip all I/O
    if not updates:
        logger.info(f"memory_write: no state changes for user {user_id} — skipping PostgreSQL write")
        return {}

    # persist preference updates to PostgreSQL
    update_user_memory(user_id, updates)

    return {}