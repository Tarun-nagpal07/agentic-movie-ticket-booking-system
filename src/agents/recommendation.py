from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import RecommendationAgentState
from src.tools.recommendation_tools import (
    get_user_preferences,
    recommend_movies_by_preference,
    recommend_theaters_for_movie,
    recommend_based_on_history
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a personalized movie recommendation assistant.
You suggest movies based on what is currently showing and the user's taste.

Tools available and when to use them:
- get_user_preferences          : ALWAYS call this first — gets city, genres, location, history
- recommend_movies_by_preference: use for "suggest a movie", "what's good", "show me sci-fi"
- recommend_based_on_history    : use for "based on my taste", "similar to before", "surprise me"
- recommend_theaters_for_movie  : ALWAYS call after picking top movie — finds nearest theaters

Strict rules:
- ALWAYS call get_user_preferences first, every time
- ONLY recommend movies showing TODAY in user's city
- for generic requests → recommend_movies_by_preference using memory genres
- for history-based requests → recommend_based_on_history
- ALWAYS follow up top recommendation with recommend_theaters_for_movie
- show match_score, genre, language, rating, and available theaters in response
- if user wants to book after recommendation → confirm movie + theater and tell them booking agent will proceed
- NEVER recommend movies not in the tool results — do not hallucinate titles
"""

recommendation_react_agent = create_agent(
    get_llm(),
    tools=[
        get_user_preferences,
        recommend_movies_by_preference,
        recommend_theaters_for_movie,
        recommend_based_on_history
    ],
    system_prompt=SYSTEM_PROMPT
)


def recommendation_node(state: RecommendationAgentState) -> RecommendationAgentState:
    logger.info(f"recommendation agent called — user: {state.get('user_id')}")

    input_messages = [
        m for m in state.get("messages", [])
        if getattr(m, "type", None) == "human" or (getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None))
    ]
    agent_state = {**state, "messages": input_messages}

    result = recommendation_react_agent.invoke(agent_state)

    # extract recommendations from tool messages if present
    recommendations    = state.get("recommendations")
    suggested_theaters = state.get("suggested_theaters")

    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", None)
        if isinstance(content, dict):
            if "recommendations" in content:
                recommendations = content["recommendations"]
            if "theaters" in content:
                suggested_theaters = content["theaters"]

    return {
        **state,
        "messages":          result["messages"][len(input_messages):],
        "recommendations":   recommendations,
        "suggested_theaters": suggested_theaters
    }