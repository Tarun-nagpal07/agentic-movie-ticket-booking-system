# src/agents/recommendation.py

from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from src.tools.recommendation_tools import (
    get_user_preferences,
    recommend_movies_by_preference,
    recommend_theaters_for_movie,
    recommend_based_on_history
)
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# llm = AzureChatOpenAI(
#     azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
#     azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
#     api_version=settings.AZURE_OPENAI_API_VERSION,
#     api_key=settings.AZURE_OPENAI_API_KEY
# )

SYSTEM_PROMPT = """
You are a movie recommendation assistant.
You suggest movies based on user preferences, history, and what is currently showing.

Tools available:
- get_user_preferences: always call this first — gets city, genres, location
- recommend_movies_by_preference: suggests movies matching genre and language
- recommend_theaters_for_movie: finds best theaters for a movie sorted by distance
- recommend_based_on_history: suggests movies based on what user watched before

Rules:
- always call get_user_preferences first
- only recommend movies showing TODAY in user's city
- for "suggest something" or "what should I watch" → recommend_movies_by_preference
- for "based on my history" or "similar to before" → recommend_based_on_history
- after recommending movies, also call recommend_theaters_for_movie for top pick
- always show match_score, rating, genre, and available theaters in response
- if user wants to book after recommendation, tell them to confirm and the booking agent will take over
"""

recommendation_agent = create_react_agent(
    llm,
    tools=[
        get_user_preferences,
        recommend_movies_by_preference,
        recommend_theaters_for_movie,
        recommend_based_on_history
    ],
    state_modifier=SYSTEM_PROMPT
)


def recommendation_node(state: dict) -> dict:
    logger.info(f"recommendation agent called for user {state.get('user_id')}")
    result = recommendation_agent.invoke(state)
    return {**state, "messages": result["messages"]}