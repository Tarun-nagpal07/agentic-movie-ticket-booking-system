from openai import OpenAI
from src.config.settings import settings
from src.utils.logger import get_logger
from src.utils.errors import RAGError, handle_errors
from langchain_huggingface import HuggingFaceEmbeddings 



EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
EMBEDDING_DIM   = "768"


embeddings = HuggingFaceEmbeddings(
            model_name = EMBEDDING_MODEL 
)
logger = get_logger(__name__)

# client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.BASE_URL)


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

    # response = client.embeddings.create(
    #     model=EMBEDDING_MODEL,
    #     input=text
    # )

    response = embeddings(input=text)
    logger.debug(f"embedding generated for text: '{text[:60]}...'")
    return response.data[0].embedding


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

    # response = client.embeddings.create(
    #     model=EMBEDDING_MODEL,
    #     input=cleaned
    # )
    response = embeddings(input=cleaned)

    logger.info(f"batch embedding: {len(cleaned)} texts embedded")
    return [item.embedding for item in response.data]