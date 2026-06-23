from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import PolicyAgentState
from src.tools.policy_tools import search_policy_docs
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages, extract_new_messages
from langchain_core.messages import AIMessage
from src.prompts.policy import SYSTEM_PROMPT

logger = get_logger(__name__)


policy_react_agent = create_agent(
    get_llm(),
    tools=[search_policy_docs],
    system_prompt=SYSTEM_PROMPT,
    middleware=[trim_messages]
)


def policy_node(state: PolicyAgentState) -> PolicyAgentState:
    logger.info(f"policy agent called — user: {state.get('user_id')}")

    input_messages = [
        m for m in state.get("messages", [])
        if getattr(m, "type", None) == "human" or (getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None))
    ]
    agent_state = {**state, "messages": input_messages}

    try:
        result = policy_react_agent.invoke(agent_state, config={"recursion_limit": 30})
    except Exception as e:
        if "recursion_limit" in str(e).lower() or "recursion" in str(e).lower():
            logger.error(f"Policy agent recursion limit reached: {e}")

            msg = AIMessage(content="I encountered a processing loop. Please try your request again with simpler terms or one step at a time.")
            return {
                **state,
                "messages": [msg]
            }
        raise e

    retrieved_chunks = state.get("retrieved_chunks")
    policy_answer    = state.get("policy_answer")

    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", None)
        if isinstance(content, dict) and "chunks" in content:
            retrieved_chunks = content["chunks"]
        if isinstance(content, str) and len(content) > 20:
            policy_answer = content

    return {
        **state,
        "messages":        extract_new_messages(input_messages, result["messages"]),
        "retrieved_chunks": retrieved_chunks,
        "policy_answer":   policy_answer
    }