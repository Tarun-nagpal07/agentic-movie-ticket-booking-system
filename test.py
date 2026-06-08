
from langchain_groq import ChatGroq
from src.config.settings import settings

groq_llm = ChatGroq(
                    model=settings.FIRST_FALLBACK_LLM,
                    api_key=settings.GROQ_API_KEY,
                    max_completion_tokens=512,
                    streaming=True,
                    reasoning_effort='low'
            )

print(groq_llm.invoke("Hey"))