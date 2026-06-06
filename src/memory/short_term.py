from langgraph.checkpoint.redis import RedisSaver
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

def get_checkpointer() -> RedisSaver:
    """
    Returns a RedisSaver checkpointer for LangGraph.
    LangGraph uses this to save and restore graph state per thread_id.
    Session TTL is handled by RedisSaver internally.
    """
    ttl_config = {
        "default_ttl": 120,          # 120 minutes (2 hours)
        "refresh_on_read": True      # reset TTL on read
    }
    checkpointer = RedisSaver(redis_url=settings.REDIS_URL, ttl=ttl_config)
    checkpointer.setup()
    logger.info("Redis checkpointer initialized with 2-hour TTL and indexes setup")
    return checkpointer

