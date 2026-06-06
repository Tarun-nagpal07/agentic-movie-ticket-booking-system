import json
from src.db.postgres import get_db_cursor
from src.utils.logger import get_logger

logger = get_logger(__name__)

def get_user_memory(user_id: str) -> dict | None:
    """
    Read user long-term memory (preferences) from PostgreSQL/Supabase.
    Returns None if user not found - caller decides fallback.
    """
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT preferences FROM user_preferences WHERE user_id = %s;",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                logger.warning(f"No long-term memory found in PostgreSQL for user {user_id}")
                return None
            
            logger.info(f"Long-term memory loaded from PostgreSQL for user {user_id}")
            # row[0] is already parsed if psycopg2 JSONB deserialization is active,
            # or it is a dict/string. Let's make sure it is handled correctly.
            preferences = row[0]
            if isinstance(preferences, str):
                return json.loads(preferences)
            return preferences
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
        with get_db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_preferences (user_id, preferences, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE
                SET preferences = EXCLUDED.preferences, updated_at = CURRENT_TIMESTAMP;
                """,
                (user_id, json.dumps(data))
            )
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
    Delete user memory from PostgreSQL/Supabase.
    """
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "DELETE FROM user_preferences WHERE user_id = %s;",
                (user_id,)
            )
            logger.info(f"Long-term memory deleted from PostgreSQL for user {user_id}")
    except Exception as e:
        logger.warning(
            "PostgreSQL unavailable while deleting long-term memory for user %s: %s",
            user_id,
            e,
            exc_info=True
        )

def update_user_memory(user_id: str, updates: dict) -> None:
    """
    Partial update — merges updates into existing memory in PostgreSQL/Supabase.
    """
    existing = get_user_memory(user_id) or {}

    # merge — lists append, scalars overwrite
    for key, value in updates.items():
        if isinstance(value, list) and isinstance(existing.get(key), list):
            # append unique items only
            existing[key] = list({
                json.dumps(item) if isinstance(item, dict) else item
                for item in existing[key] + value
            })
            # if it's booking_history — deserialize back
            if key == "booking_history":
                existing[key] = [
                    json.loads(i) if isinstance(i, str) else i
                    for i in existing[key]
                ]
        else:
            existing[key] = value

    save_user_memory(user_id, existing)
    logger.info(f"Long-term memory updated in PostgreSQL for user {user_id}: fields {list(updates.keys())}")
