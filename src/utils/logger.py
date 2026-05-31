import logging
import sys
from src.config.settings import settings

def get_logger(name: str) -> logging.Logger:
    """set up a logger with the specified name and confriguration"""

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # already configured
    
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(handler)
    logger.propagate = False  # prevent double logging if root logger is also configured
    return logger