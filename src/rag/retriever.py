from src.rag.embeddings import get_embedding
from src.rag.qdrant_client import get_qdrant_client
from src.config.constants import QdrantCollection, Limits
from src.utils.logger import get_logger
from src.utils.errors import RAGError, handle_errors

logger = get_logger(__name__)


@handle_errors(error_class=RAGError)
def retrieve_policy_chunks(query: str, top_k: int = Limits.RAG_TOP_K) -> list[dict]:
    """
    Retrieves top-K relevant policy chunks from Qdrant for a given query.
    Returns chunks with text, source, and relevance score.
    """
    client    = get_qdrant_client()
    embedding = get_embedding(query)

    response = client.query_points(
        collection_name=QdrantCollection.POLICY_DOCS,
        query=embedding,
        limit=top_k,
        with_payload=True
    )

    results = response.points

    if not results:
        logger.warning(f"no policy chunks found for query: '{query}'")
        return []

    chunks = [
        {
            "text":   r.payload["text"],
            "source": r.payload["source"],
            "score":  round(r.score, 3)
        }
        for r in results
    ]

    logger.info(f"retrieved {len(chunks)} policy chunks for query: '{query[:60]}'")
    return chunks