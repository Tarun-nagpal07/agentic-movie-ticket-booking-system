import json
from src.api import services
from src.utils.logger import get_logger

logger = get_logger(__name__)

def get_user_memory(user_id: str) -> dict | None:
    """
    Read user long-term memory (preferences and profile) from PostgreSQL/Supabase.
    """
    try:
        user = services.get_user_by_id(user_id, include_bookings=False)
        if not user:
            logger.warning(f"No user memory found in PostgreSQL for user {user_id}")
            return None
        logger.info(f"Long-term memory loaded from PostgreSQL for user {user_id}")
        return user
    except Exception as e:
        logger.warning(
            "PostgreSQL unavailable while loading long-term memory for user %s: %s",
            user_id,
            e,
            exc_info=True
        )
        return None

def save_user_memory(user_id: str, data: dict) -> None:
    """
    Write updated user memory to PostgreSQL/Supabase.
    """
    try:
        services.update_user_preferences(user_id, data)
        logger.info(f"Long-term memory saved in PostgreSQL for user {user_id}")
    except Exception as e:
        logger.warning(
            "PostgreSQL unavailable while saving long-term memory for user %s: %s",
            user_id,
            e,
            exc_info=True
        )

def delete_user_memory(user_id: str) -> None:
    """
    Delete user memory (cannot fully delete user profile, so just resets preferences).
    """
    try:
        empty_prefs = {
            "favorite_genres": [],
            "preferred_theaters": [],
            "preferred_seat_type": None,
            "preferred_format": None,
            "language_pref": "English"
        }
        services.update_user_preferences(user_id, empty_prefs)
        logger.info(f"Long-term memory deleted/reset from PostgreSQL for user {user_id}")
    except Exception as e:
        logger.warning(
            "PostgreSQL unavailable while deleting long-term memory for user %s: %s",
            user_id,
            e,
            exc_info=True
        )

def update_user_memory(user_id: str, updates: dict) -> None:
    """
    Partial update — merges updates into existing preferences in PostgreSQL.
    """
    existing = get_user_memory(user_id) or {}

    # merge — lists append, scalars overwrite
    for key, value in updates.items():
        if key == "booking_history":
            # booking history is read-only, managed by bookings database table mutations
            continue
        if isinstance(value, list) and isinstance(existing.get(key), list):
            # append unique items only
            existing[key] = list({
                json.dumps(item) if isinstance(item, dict) else item
                for item in existing[key] + value
            })
        else:
            existing[key] = value

    save_user_memory(user_id, existing)
    logger.info(f"Long-term memory updated in PostgreSQL for user {user_id}: fields {list(updates.keys())}")
