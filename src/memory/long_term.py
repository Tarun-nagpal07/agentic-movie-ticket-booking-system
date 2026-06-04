import json
import redis
from redis.exceptions import RedisError
from src.config.settings import settings
from src.config.constants import RedisPrefix
from src.utils.logger import get_logger


logger = get_logger(__name__)

# single Redis connection — reused across calls
redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)


def _user_key(user_id:str) -> str:
    return f"{RedisPrefix.USER}{user_id}"

def get_user_memory(user_id: str)-> dict | None:
    """
    Read user long-term memory from Redis.
    Returns None if user not found - caller decides fallback.
    """
    try:
        raw = redis_client.get(_user_key(user_id))
    except RedisError as e:
        logger.warning(
            "Redis unavailable while loading long-term memory for user %s: %s",
            user_id,
            e,
        )
        return None

    if not raw:
        logger.warning(f"no long-term memory found for user {user_id}")
        return None
    
    logger.info(f"long-term memory loaded for user {user_id}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Invalid long-term memory JSON for user %s: %s", user_id, e)
        return None


def save_user_memory(user_id: str, data: dict) -> None:
    """
    Write updated user memory to Redis.
    No TTL — long-term memory persists forever.
    """
    try:
        redis_client.set(_user_key(user_id), json.dumps(data))
        logger.info(f"long-term memory saved for user {user_id}")
    except RedisError as e:
        logger.warning(
            "Redis unavailable while saving long-term memory for user %s: %s",
            user_id,
            e,
        )


def delete_user_memory(user_id: str) -> None:
    """
    Delete user memory from Redis.
    Only used for testing or user data deletion.
    """
    try:
        redis_client.delete(_user_key(user_id))
        logger.info(f"long-term memory deleted for user {user_id}")
    except RedisError as e:
        logger.warning(
            "Redis unavailable while deleting long-term memory for user %s: %s",
            user_id,
            e,
        )


def update_user_memory(user_id: str, updates: dict) -> None:
    """
    Partial update — merges updates into existing memory.
    Use this instead of save_user_memory when only a few fields change.
    """
    existing = get_user_memory(user_id) or {}

    # merge — lists append, scalars overwrite
    for  key, value in updates.items():
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

    try:
        redis_client.set(_user_key(user_id), json.dumps(existing))
        logger.info(f"long-term memory updated for user {user_id}: fields {list(updates.keys())}")
    except RedisError as e:
        logger.warning(
            "Redis unavailable while updating long-term memory for user %s: %s",
            user_id,
            e,
        )
