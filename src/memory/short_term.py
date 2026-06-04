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
    checkpointer = RedisSaver(redis_url=settings.REDIS_URL)
    checkpointer.setup()
    logger.info("Redis checkpointer initialized and indexes setup")
    return checkpointer

