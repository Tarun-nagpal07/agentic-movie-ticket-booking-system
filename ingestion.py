import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.rag.indexer import index_policy_docs
from src.utils.logger import get_logger

logger = get_logger(__name__)

if __name__ == "__main__":
    force = "--force" in sys.argv

    logger.info("starting policy ingestion...")
    index_policy_docs(force=force)
    logger.info("done.")