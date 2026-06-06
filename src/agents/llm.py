from langchain.chat_models import init_chat_model
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from src.config.settings import settings
from src.utils.errors import ModelError, handle_errors
from src.utils.logger import get_logger

logger = get_logger(__name__)


@handle_errors(error_class=ModelError)
def get_llm(structure: bool = False):
    primary_model = init_chat_model(
        model=settings.LLM_MODEL,
        api_key=settings.API_KEY,
        base_url=settings.BASE_URL,
        streaming=not structure
    )

    fallbacks = []

    # Hugging Face serverless endpoints do not support Pydantic schema function calling (with_structured_output)
    if settings.HF_TOKEN and not structure:
        logger.info("Configuring Llama-3.1-70B-Instruct via Hugging Face as fallback LLM.")
        try:
            llama_endpoint = HuggingFaceEndpoint(
                repo_id=settings.FIRST_FALLBACK_LLM,
                huggingfacehub_api_token=settings.HF_TOKEN,
                max_new_tokens=512,
                temperature=0.01,
                streaming=True
            )
            llama_model = ChatHuggingFace(llm=llama_endpoint)
            fallbacks.append(llama_model)
        except Exception as e:
            logger.error(f"Failed to initialize Llama Hugging Face fallback: {e}")

    if fallbacks:
        return primary_model.with_fallbacks(fallbacks=fallbacks)

    return primary_model
