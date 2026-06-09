from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from src.config.settings import settings
from src.config.constants import QdrantCollection
from src.rag.embeddings import EMBEDDING_DIM
from src.utils.logger import get_logger

logger = get_logger(__name__)

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.QDRANT_URL)
        logger.info(f"Qdrant client connected to {settings.QDRANT_URL}")
    return _client


def ensure_collections() -> None:
    """
    Creates Qdrant collections if they don't exist.
    Safe to call on every startup — skips if already exists.
    """
    client = get_qdrant_client()

    for collection_name in [
        QdrantCollection.POLICY_DOCS
    ]:
        existing = [c.name for c in client.get_collections().collections]

        if collection_name not in existing:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Qdrant collection created: {collection_name}")
        else:
            logger.info(f"Qdrant collection already exists: {collection_name}")