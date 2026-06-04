from langgraph.prebuilt import create_react_agent
from src.agents.llm import get_llm
from src.graph.state import PolicyAgentState
from src.tools.policy_tools import search_policy_docs
from src.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a policy and FAQ assistant for a movie ticket booking system.
You answer questions about rules, refunds, cancellations, and general policies.

Tools available:
- search_policy_docs : searches policy documents for relevant rules and answers

Strict rules:
- ALWAYS call search_policy_docs before answering — never answer from memory alone
- use the retrieved chunks as your source of truth
- if chunks do not contain the answer → say "I don't have information on that"
  do NOT guess or hallucinate policy rules
- always cite which policy the answer comes from (use source field from chunks)
- for cancellation questions → always include:
    * refund percentages for each time window
    * refund processing timeline
- for seat questions → include booking cutoff times
- keep answers concise and structured — use bullet points for rules
- if user seems to be asking in order to cancel → suggest they go ahead with cancellation agent

Topics you handle:
- cancellation rules and windows
- refund percentages and timelines
- payment methods accepted
- seat booking rules and cutoffs
- children entry policies
- food and beverage policies
- group booking rules
"""

policy_react_agent = create_react_agent(
    get_llm(),
    tools=[search_policy_docs],
    state_modifier=SYSTEM_PROMPT
)


def policy_node(state: PolicyAgentState) -> PolicyAgentState:
    logger.info(f"policy agent called — user: {state.get('user_id')}")

    result = policy_react_agent.invoke(state)

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
        "messages":        result["messages"],
        "retrieved_chunks": retrieved_chunks,
        "policy_answer":   policy_answer
    }