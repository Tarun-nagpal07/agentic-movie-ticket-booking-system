import uuid
import json
from pathlib import Path
from qdrant_client.models import PointStruct
from src.rag.embeddings import get_embeddings_batch
from src.rag.qdrant_client import get_qdrant_client, ensure_collections
from src.config.constants import QdrantCollection
from src.utils.logger import get_logger

logger = get_logger(__name__)

POLICY_FILE  = Path(__file__).parent.parent.parent / "data" / "policy.json"


def load_policy_json(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"policy.json not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("policies", [])


def index_policy_docs(force: bool = False) -> None:
    """
    One-time indexing script.
    Reads policy.json → embeds → stores in Qdrant.

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

    # load policy json
    logger.info(f"loading policy from {POLICY_FILE}")
    policies = load_policy_json(POLICY_FILE)

    if not policies:
        raise ValueError("policy.json is empty or has no policies — nothing to index")

    # batch embed all policy texts
    texts      = [p["text"] for p in policies]
    embeddings = get_embeddings_batch(texts)

    # build Qdrant points
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embeddings[i],
            payload={
                "chunk_id": p["chunk_id"],
                "topic":    p.get("topic", "general"),
                "text":     p["text"],
                "source":   "policy.json"
            }
        )
        for i, p in enumerate(policies)
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