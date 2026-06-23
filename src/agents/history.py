from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import HistoryAgentState
from src.tools.history_tools import make_history_tools
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages, extract_new_messages
from langchain_core.messages import AIMessage
from src.prompts.history import SYSTEM_PROMPT

logger = get_logger(__name__)



def history_node(state: HistoryAgentState) -> HistoryAgentState:
    user_id = state.get("user_id")
    logger.info(f"history agent called — user: {user_id}")

    # Build tools bound to this user's context for this invocation
    tools = make_history_tools(user_id=user_id)

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
            logger.error(f"History agent recursion limit reached: {e}")

            msg = AIMessage(content="I encountered a processing loop. Please try your request again with simpler terms or one step at a time.")
            return {
                **state,
                "messages": [msg]
            }
        raise e
    return {
        **state,
        "messages": extract_new_messages(input_messages, result["messages"]),
        "poster_next_node": "end"
    }