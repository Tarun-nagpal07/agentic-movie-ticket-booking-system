import os
import sys
from pydantic import BaseModel

sys.path.insert(0, "/Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system")

# load settings to populate env variables
from src.config.settings import settings
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

from langchain.chat_models import init_chat_model

class MovieTitleList(BaseModel):
    titles: list[str]

def test_extraction():
    llm = init_chat_model(
        model=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.BASE_URL,
        streaming=False
    ).with_structured_output(MovieTitleList)

    text = "Sure, I recommend watching Pathaan or Interstellar today! Kalki 2898 AD is also a great choice."
    res = llm.invoke(f"Extract ALL movie titles explicitly mentioned in the following text. Return only real movie names that appear in the text, nothing else.\n\nText: {text}")
    print("Extracted titles:", res.titles)

if __name__ == "__main__":
    test_extraction()
