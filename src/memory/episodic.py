import uuid
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from src.rag.embeddings import get_embedding
from src.rag.qdrant_client import get_qdrant_client
from src.config.constants import QdrantCollection
from src.config.settings import settings
from src.utils.logger import get_logger
from src.utils.errors import MemoryError, handle_errors
from src.agents.llm import get_llm
logger = get_logger(__name__)


@handle_errors(error_class=MemoryError)
def store_session_summary(user_id: str, thread_id: str, summary: str) -> None:
    """
    Embeds and stores a session summary in Qdrant after conversation ends.
    Called by memory agent at end of every session.
    """
    client    = get_qdrant_client()
    embedding = get_embedding(summary)

    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=embedding,
        payload={
            "user_id":    user_id,
            "thread_id":  thread_id,
            "summary":    summary,
            "created_at": datetime.utcnow().isoformat()
        }
    )

    client.upsert(
        collection_name=QdrantCollection.SESSION_MEMORY,
        points=[point]
    )

    logger.info(f"session summary stored for user {user_id}, thread {thread_id}")


@handle_errors(error_class=MemoryError)
def get_relevant_sessions(user_id: str, query: str, top_k: int = 3) -> list[dict]:
    """
    Retrieves past session summaries semantically similar to current query.
    Called at start of session to inject relevant history into context.
    """
    client    = get_qdrant_client()
    embedding = get_embedding(query)

    response = client.query_points(
        collection_name=QdrantCollection.SESSION_MEMORY,
        query=embedding,
        limit=top_k,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                )
            ]
        )
    )

    results = response.points

    sessions = [
        {
            "summary":    r.payload["summary"],
            "created_at": r.payload["created_at"],
            "score":      round(r.score, 3)
        }
        for r in results
    ]

    logger.info(f"found {len(sessions)} relevant past sessions for user {user_id}")
    return sessions


@handle_errors(error_class=MemoryError)
def summarize_session(messages: list[dict]) -> str:
    """
    Summarizes a conversation using Azure OpenAI.
    Called at end of session before storing to Qdrant.
    """
    llm = get_llm()

    # only keep human and assistant messages — skip tool messages
    # LangGraph messages are objects with .type and .content, not dicts
    clean_messages = []
    for m in messages:
        msg_type = getattr(m, "type", None)
        content  = getattr(m, "content", None)
        if msg_type in ("human", "ai") and isinstance(content, str):
            role = "USER" if msg_type == "human" else "ASSISTANT"
            clean_messages.append({"role": role, "content": content})

    if not clean_messages:
        return ""

    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in clean_messages
    )

    response = llm.invoke([
        {
            "role": "system",
            "content": "Summarize this movie booking conversation in 2-3 sentences. "
                       "Include what the user searched for, booked, or cancelled."
        },
        {
            "role": "user",
            "content": conversation_text
        }
    ])

    summary = response.content.strip()
    logger.info(f"session summarized: {summary[:80]}...")
    return summary