from src.graph.state import MemoryAgentState, BookingState
from src.memory.long_term import get_user_memory, update_user_memory
from src.memory.episodic import summarize_session, store_session_summary
from src.db.json_store import load_db, save_db
from src.config.constants import DBFile
from src.utils.logger import get_logger

logger = get_logger(__name__)


def memory_read_node(state: BookingState) -> BookingState:
    """
    Runs at graph START.
    Loads long-term user memory from Redis into state["memory"].
    Also fetches relevant past sessions from Qdrant.
    """
    from src.memory.episodic import get_relevant_sessions

    user_id  = state["user_id"]
    messages = state.get("messages", [])

    user_memory = get_user_memory(user_id)

    # fallback — load from users.json if Redis miss
    if not user_memory:
        logger.warning(f"Redis miss for user {user_id} — falling back to users.json")
        users_db    = load_db(DBFile.USERS)
        user_memory = users_db["users"].get(user_id)

    # inject relevant past sessions into context
    last_message = ""
    for m in reversed(messages):
        if isinstance(m.get("content"), str):
            last_message = m["content"]
            break

    past_sessions = []
    if last_message:
        past_sessions = get_relevant_sessions(user_id, last_message)

    logger.info(f"memory_read complete for user {user_id}")
    return {
        **state,
        "memory":       user_memory or {},
        "past_sessions": past_sessions
    }


def memory_write_node(state: MemoryAgentState) -> MemoryAgentState:
    """
    Runs at graph END.
    Writes updates back to Redis long-term memory.
    Summarizes session and stores in Qdrant episodic memory.
    Also syncs changes back to users.json.
    """
    user_id   = state["user_id"]
    thread_id = state.get("thread_id", "unknown")
    messages  = state.get("messages", [])
    confirmed = state.get("confirmed")
    updates   = {}

    # booking confirmed 
    if confirmed and state.get("booking_draft"):
        draft = state["booking_draft"]

        updates["booking_history"] = [draft]
        updates["preferred_theaters"] = [draft["theater_id"]]

        # infer seat type from booked seats using seat_types map
        if draft.get("seats") and draft.get("seat_types"):
            row           = draft["seats"][0][0]          # e.g "E" from "E5"
            seat_type     = draft["seat_types"].get(row)
            if seat_type:
                updates["preferred_seat_type"] = seat_type

        # infer format preference
        if draft.get("format"):
            updates["preferred_format"] = draft["format"]

        logger.info(f"memory_write: booking {draft['booking_id']} added for user {user_id}")

    # cancellation confirmed 
    if state.get("cancel_draft"):
        draft = state["cancel_draft"]
        if draft.get("status") == "cancelled":
            updates["booking_history"] = [draft]
            logger.info(f"memory_write: cancellation {draft['booking_id']} recorded for user {user_id}")

    #  persist to Redis 
    if updates:
        update_user_memory(user_id, updates)

        # sync back to users.json as well
        users_db = load_db(DBFile.USERS)
        if user_id in users_db["users"]:
            current = users_db["users"][user_id]
            for key, value in updates.items():
                if isinstance(value, list) and isinstance(current.get(key), list):
                    # append unique items
                    existing_ids = {
                        b.get("booking_id") for b in current[key]
                        if isinstance(b, dict)
                    }
                    new_items = [
                        b for b in value
                        if isinstance(b, dict) and b.get("booking_id") not in existing_ids
                    ]
                    current[key] = current[key] + new_items
                else:
                    current[key] = value
            users_db["users"][user_id] = current
            save_db(DBFile.USERS, users_db)

    #  episodic memory 
    if messages:
        summary = summarize_session(messages)
        if summary:
            store_session_summary(user_id, thread_id, summary)
            logger.info(f"memory_write: session summary stored for user {user_id}")

    return state