from langchain.tools import tool
from src.rag.retriever import retrieve_policy_chunks
from src.config.constants import Limits
from src.utils.errors import handle_errors, RAGError
from src.utils.logger import get_logger
from src.schemas.policy import PolicySearchRequest

logger = get_logger(__name__)


@tool("search_policy_docs", args_schema=PolicySearchRequest)
@handle_errors(error_class=RAGError)
def search_policy_docs(query: str, top_k: int = Limits.RAG_TOP_K) -> dict:
    """
    Search policy documents for rules, FAQs, cancellation terms, and refund policies.
    Use for any question about booking rules, seat policies, payment methods, or refunds.

    Args:
        query: natural language question e.g. "what is the cancellation refund policy?"
        top_k: number of chunks to retrieve, default 3
    """
    chunks = retrieve_policy_chunks(query, top_k)

    if not chunks:
        return {
            "status": "not_found",
            "message": "No relevant policy information found for this query.",
            "chunks": []
        }

    return {
        "status": "success",
        "chunks": chunks
    }