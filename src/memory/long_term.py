import json
import redis
from src.config.settings import settings
from src.config.constants import RedisPrefix
from src.utils.logger import get_logger
from src.utils.errors import MemoryError, handle_errors


logger = get_logger(__name__)

# single Redis connection — reused across calls
redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)


def _user_key(user_id:str) -> str:
    return f"{RedisPrefix.USER}{user_id}"

@handle_errors(error_class=MemoryError)
def get_user_memory(user_id: str)-> dict | None:
    """
    Read user long-term memory from Redis.
    Returns None if user not found - caller decides fallback.
    """
    raw = redis_client.get(_user_key(user_id))

    if not raw:
        logger.warning(f"no long-term memory found for user{user_id}")
        return None
    
    logger.info(f"long-term memory loaded for user{user_id}")
    return json.loads(raw)


@handle_errors(error_class=MemoryError)
def save_user_memory(user_id: str, data: dict) -> None:
    """
    Write updated user memory to Redis.
    No TTL — long-term memory persists forever.
    """
    redis_client.set(_user_key(user_id), json.dumps(data))
    logger.info(f"long-term memory saved for user {user_id}")


@handle_errors(error_class=MemoryError)
def delete_user_memory(user_id: str) -> None:
    """
    Delete user memory from Redis.
    Only used for testing or user data deletion.
    """
    redis_client.delete(_user_key(user_id))
    logger.info(f"long-term memory deleted for user {user_id}")


@handle_errors(error_class=MemoryError)
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

    redis_client.set(_user_key(user_id), json.dumps(existing))
    logger.info(f"long-term memory updated for user {user_id}: fields {list(updates.keys())}")
