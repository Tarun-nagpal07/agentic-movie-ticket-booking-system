import uuid
from pathlib import Path
from qdrant_client.models import PointStruct
from src.rag.embeddings import get_embeddings_batch
from src.rag.qdrant_client import get_qdrant_client, ensure_collections
from src.config.constants import QdrantCollection
from src.utils.logger import get_logger

logger = get_logger(__name__)

POLICY_FILE  = Path(__file__).parent.parent.parent / "data" / "policy.txt"
CHUNK_SIZE   = 300    # characters per chunk
CHUNK_OVERLAP = 50    # overlap between chunks to preserve context


def load_policy_txt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"policy.txt not found at {path}")
    return path.read_text(encoding="utf-8")


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """
    Splits text into overlapping chunks.
    Each chunk carries its source line range for citation.
    """
    chunks   = []
    start    = 0
    chunk_id = 0

    while start < len(text):
        end   = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append({
                "chunk_id": chunk_id,
                "text":     chunk,
                "start":    start,
                "end":      min(end, len(text))
            })
            chunk_id += 1

        start = end - overlap   # overlap for context continuity

    logger.info(f"split policy.txt into {len(chunks)} chunks")
    return chunks


def index_policy_docs(force: bool = False) -> None:
    """
    One-time indexing script.
    Reads policy.txt → splits into chunks → embeds → stores in Qdrant.

    Args:
        force: if True, deletes existing collection and reindexes from scratch
    """
    client = get_qdrant_client()
    ensure_collections()

    # check if already indexed
    if not force:
        count = client.count(collection_name=QdrantCollection.POLICY_DOCS).count
        if count > 0:
            logger.info(f"policy already indexed ({count} chunks) — skipping. Use force=True to reindex.")
            return

    if force:
        client.delete_collection(QdrantCollection.POLICY_DOCS)
        ensure_collections()
        logger.info("existing policy collection deleted — reindexing from scratch")

    # load and split
    logger.info(f"loading policy from {POLICY_FILE}")
    raw_text = load_policy_txt(POLICY_FILE)
    chunks   = split_into_chunks(raw_text)

    if not chunks:
        raise ValueError("policy.txt is empty — nothing to index")

    # batch embed all chunks
    texts      = [c["text"] for c in chunks]
    embeddings = get_embeddings_batch(texts)

    # build Qdrant points
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embeddings[i],
            payload={
                "chunk_id": chunk["chunk_id"],
                "text":     chunk["text"],
                "source":   "policy.txt",
                "start":    chunk["start"],
                "end":      chunk["end"]
            }
        )
        for i, chunk in enumerate(chunks)
    ]

    # upsert in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        client.upsert(
            collection_name=QdrantCollection.POLICY_DOCS,
            points=batch
        )
        logger.info(f"indexed batch {i // batch_size + 1} — {len(batch)} chunks")

    logger.info(f"policy indexing complete — {len(points)} chunks stored in Qdrant")