from langchain.agents import create_agent
import json
from src.agents.llm import get_llm
from src.graph.state import RecommendationAgentState
from src.tools.recommendation_tools import make_recommendation_tools
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages, extract_new_messages
from src.utils.id_cleaner import remove_raw_ids
from langchain_core.messages import AIMessage
from src.prompts.recommendation import SYSTEM_PROMPT

logger = get_logger(__name__)



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