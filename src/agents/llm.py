from langchain.chat_models import init_chat_model
from src.config.settings import settings
from src.utils.errors import ModelError,handle_errors


@handle_errors(error_class=ModelError)
def get_llm():
    model = init_chat_model(
            model=settings.LLM_MODEL,
            api_key = settings.API_KEY,
            base_url= settings.BASE_URL
        )

    return model
