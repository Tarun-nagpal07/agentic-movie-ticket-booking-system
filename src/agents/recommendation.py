from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import RecommendationAgentState
from src.tools.recommendation_tools import make_recommendation_tools
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages, extract_new_messages
from src.utils.id_cleaner import remove_raw_ids
from langchain_core.messages import AIMessage

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a personalized movie recommendation assistant.
You suggest movies based on what is currently showing and the user's taste.

[CRITICAL RULE: CONCEAL ALL DATABASE IDS]
- NEVER display, print, or mention raw database IDs (such as theater_id, movie_id, e.g. 't1', 'm2') in your final text responses or listings shown to the user.
- If a tool returns IDs, keep them hidden in the background for tool calling purposes. ONLY present the readable theater names, movie titles, show times, and addresses to the user.
- DO NOT print "(Theater ID: ...)" or "(Movie ID: ...)" or "(ID: ...)" in your output.

Tools available and when to use them:
- get_user_preferences          : ALWAYS call this first — gets city, genres, location, history
- recommend_movies_by_preference: use for "suggest a movie", "what's good", "show me sci-fi"
- recommend_based_on_history    : use for "based on my taste", "similar to before", "surprise me"
- recommend_theaters_for_movie  : ALWAYS call after picking top movie — finds nearest theaters

Strict rules:
- NEVER guess any movie titles, theater names, show times, locations, or ratings. ONLY use the exact values returned by the tools. If no movies or theaters are found, state that clearly instead of guessing/inventing them.
- ALWAYS call get_user_preferences first, every time
- ONLY recommend movies showing TODAY in user's city
- for generic requests → recommend_movies_by_preference using memory genres
- for history-based requests → recommend_based_on_history
- ALWAYS follow up top recommendation with recommend_theaters_for_movie
- show match_score, genre, language, rating, and available theaters in response
- if user wants to book after recommendation → confirm movie + theater and tell them booking agent will proceed
- NEVER recommend movies not in the tool results — do not hallucinate titles
"""


def recommendation_node(state: RecommendationAgentState) -> RecommendationAgentState:
    user_id = state.get("user_id")
    memory  = state.get("memory", {})
    logger.info(f"recommendation agent called — user: {user_id}")

    # Build tools bound to this user's context for this invocation
    tools = make_recommendation_tools(user_id=user_id, memory=memory)

    react_agent = create_agent(
        get_llm(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[trim_messages]
    )

    input_messages = [
        m for m in state.get("messages", [])
        if getattr(m, "type", None) == "human" or (getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None))
    ]
    agent_state = {**state, "messages": input_messages}

    try:
        result = react_agent.invoke(agent_state, config={"recursion_limit": 30})
    except Exception as e:
        if "recursion_limit" in str(e).lower() or "recursion" in str(e).lower():
            logger.error(f"Recommendation agent recursion limit reached: {e}")
            msg = AIMessage(content="I encountered a processing loop. Please try your request again with simpler terms or one step at a time.")
            return {
                **state,
                "messages": [msg]
            }
        raise e

    # extract recommendations from tool messages if present
    recommendations    = state.get("recommendations")
    suggested_theaters = state.get("suggested_theaters")

    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            import json
            try:
                content = json.loads(content)
            except Exception:
                pass
        if isinstance(content, dict):
            if "recommendations" in content:
                recommendations = content["recommendations"]
            if "theaters" in content:
                suggested_theaters = content["theaters"]

    returned_messages = extract_new_messages(input_messages, result["messages"])
    cleaned_messages = []
    for msg in returned_messages:
        if msg.type == "ai" and isinstance(msg.content, str):
            cleaned_messages.append(AIMessage(
                content=remove_raw_ids(msg.content),
                id=getattr(msg, "id", None),
                additional_kwargs=getattr(msg, "additional_kwargs", {}),
                response_metadata=getattr(msg, "response_metadata", {}),
                tool_calls=getattr(msg, "tool_calls", [])
            ))
        else:
            cleaned_messages.append(msg)

    res = {
        **state,
        "messages":           cleaned_messages,
        "recommendations":    recommendations,
        "suggested_theaters": suggested_theaters,
        "poster_next_node":   "memory_write"
    }
    if recommendations and isinstance(recommendations, list) and len(recommendations) > 0:
        top_movie = recommendations[0]
        res["movie_id"] = top_movie.get("movie_id")
        res["movie_title"] = top_movie.get("title")
    return res