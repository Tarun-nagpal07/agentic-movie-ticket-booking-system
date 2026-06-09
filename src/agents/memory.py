from src.graph.state import MemoryAgentState, BookingState
from src.memory.long_term import get_user_memory, update_user_memory
from src.db.json_store import load_db, save_db
from src.config.constants import DBFile
from src.utils.logger import get_logger

logger = get_logger(__name__)


def memory_read_node(state: BookingState) -> BookingState:
    """
    Runs at graph START on every turn.

    Optimization — skip expensive Redis reads after the first turn:
    - LangGraph's checkpointer already persists the full BookingState (including
      `memory`) between turns via Redis.
    - So on turn 2+ the checkpoint already carries these values — no need to
      re-read from the separate user:{user_id} key.
    - Only do the full load when the session is fresh (memory not yet in state).
    """
    user_id  = state["user_id"]

    # ── Already loaded from a previous turn's checkpoint — skip ──────────────
    if state.get("memory"):
        logger.info(f"memory_read: state already has memory for user {user_id} — skipping load")
        return {}   # no state changes needed; checkpoint carries everything

    # ── Fresh session — load from PostgreSQL (long-term store) ───────────────
    logger.info(f"memory_read: fresh session for user {user_id} — loading from PostgreSQL")
    user_memory = get_user_memory(user_id)

    # fallback — load from users.json if PostgreSQL has no entry yet
    if not user_memory:
        logger.warning(f"PostgreSQL miss for user {user_id} — falling back to users.json")
        users_db    = load_db(DBFile.USERS)
        user_memory = users_db["users"].get(user_id)

    logger.info(f"memory_read complete for user {user_id}: loaded memory")
    return {
        "memory":        user_memory or {}
    }


def memory_write_node(state: MemoryAgentState) -> MemoryAgentState:
    """
    Runs at graph END.

    Optimization — only do expensive work when something meaningful happened:
    - PostgreSQL user memory update → only when a booking/cancellation is confirmed
    - users.json sync               → same condition
    - LLM summarize + Qdrant        → only on confirmed booking or cancellation
      (skipped for recommendation, policy, history, seat-selection turns)
    """
    user_id   = state["user_id"]
    thread_id = state.get("thread_id", "unknown")
    messages  = state.get("messages", [])
    confirmed = state.get("confirmed")
    updates   = {}

    # ── booking confirmed ─────────────────────────────────────────────────────
    if confirmed and state.get("booking_draft"):
        draft = state["booking_draft"]

        updates["booking_history"]    = [draft]
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

    # ── cancellation confirmed ────────────────────────────────────────────────
    if state.get("cancel_draft"):
        draft = state["cancel_draft"]
        if draft.get("status") == "cancelled":
            updates["booking_history"] = [draft]
            logger.info(f"memory_write: cancellation {draft['booking_id']} recorded for user {user_id}")

    # ── nothing meaningful happened — skip all I/O ────────────────────────────
    # (recommendation, policy query, seat selection, history browsing, etc.)
    if not updates:
        logger.info(f"memory_write: no state changes for user {user_id} — skipping PostgreSQL/Qdrant write")
        return {}

    # ── persist preference updates to PostgreSQL ──────────────────────────────
    update_user_memory(user_id, updates)

    # sync back to users.json so it stays consistent as a fallback source
    users_db = load_db(DBFile.USERS)
    if user_id in users_db["users"]:
        current = users_db["users"][user_id]
        for key, value in updates.items():
            if isinstance(value, list) and isinstance(current.get(key), list):
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

    return {}