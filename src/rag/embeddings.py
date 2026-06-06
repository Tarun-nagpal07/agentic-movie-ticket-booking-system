from openai import OpenAI
from src.config.settings import settings
from src.utils.logger import get_logger
from src.utils.errors import RAGError, handle_errors

EMBEDDING_DIM   = "1536"

logger = get_logger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.BASE_URL)

EMBEDDING_MODEL = "text-embedding-3-small"


@handle_errors(error_class=RAGError)
def get_embedding(text: str) -> list[float]:
    """
    Returns embedding vector for a given text string.
    Used for both indexing policy chunks and querying.
    """
    text = text.strip().replace("\n", " ")

    if not text:
        raise RAGError(
            message="Cannot embed empty text.",
            code="EMPTY_TEXT",
            recoverable=False
        )

    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as primary_exc:
        logger.warning(f"Primary embedding API failed: {primary_exc}. Trying OpenRouter fallback...")
        if not settings.OPENROUTER_API_KEY:
            logger.error("OPENROUTER_API_KEY is not configured. Cannot run fallback.")
            raise primary_exc
        
        try:
            or_client = OpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1"
            )
            response = or_client.embeddings.create(
                model="openai/text-embedding-3-small",
                input=text,
                encoding_format="float"
            )
            logger.info("Successfully fetched embedding from OpenRouter fallback.")
            return response.data[0].embedding
        except Exception as fallback_exc:
            logger.error(f"OpenRouter embedding fallback also failed: {fallback_exc}")
            raise fallback_exc


@handle_errors(error_class=RAGError)
def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Batch embed multiple texts in one API call.
    More efficient than calling get_embedding() in a loop.
    """
    cleaned = [t.strip().replace("\n", " ") for t in texts]

    if not cleaned:
        raise RAGError(
            message="Empty batch provided.",
            code="EMPTY_BATCH",
            recoverable=False
        )

    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=cleaned
        )
        return [item.embedding for item in response.data]
    except Exception as primary_exc:
        logger.warning(f"Primary batch embedding API failed: {primary_exc}. Trying OpenRouter fallback...")
        if not settings.OPENROUTER_API_KEY:
            logger.error("OPENROUTER_API_KEY is not configured. Cannot run fallback.")
            raise primary_exc
        
        try:
            or_client = OpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1"
            )
            response = or_client.embeddings.create(
                model="openai/text-embedding-3-small",
                input=cleaned,
                encoding_format="float"
            )
            logger.info("Successfully fetched batch embeddings from OpenRouter fallback.")
            return [item.embedding for item in response.data]
        except Exception as fallback_exc:
            logger.error(f"OpenRouter batch embedding fallback also failed: {fallback_exc}")
            raise fallback_exc