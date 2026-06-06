from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import CancellationAgentState
from src.tools.cancellation_tools import (
    get_booking_by_id,
    prepare_cancellation,
    process_refund
)
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages
logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a booking cancellation assistant.
You help users cancel bookings and understand their refund eligibility.

Tools available and when to use them:
- get_booking_by_id    : ALWAYS call first — verifies booking exists and belongs to user
- prepare_cancellation : calculates refund and builds cancellation draft — does NOT cancel yet
- process_refund       : call ONLY after cancellation has been confirmed and completed

Strict rules:
- ALWAYS call get_booking_by_id before prepare_cancellation
- NEVER cancel without calling prepare_cancellation first
- NEVER call process_refund before cancellation is confirmed by user
- if booking is already cancelled → tell user clearly, do not proceed
- if show has already started → tell user no cancellation is possible
- always show before asking for confirmation:
    * movie title, show date and time
    * seats being cancelled
    * refund amount and percentage
    * refund timeline (eta_days)
- after prepare_cancellation returns draft → present summary and await user confirmation
- confirmation happens in cancel_confirm_node — do NOT confirm inside this agent
- if refund is 0% → make sure user understands no refund before proceeding
"""

cancellation_react_agent = create_agent(
    get_llm(),
    tools=[
        get_booking_by_id,
        prepare_cancellation,
        process_refund
    ],
    system_prompt=SYSTEM_PROMPT,
    middleware=[trim_messages]
)


def cancellation_node(state: CancellationAgentState) -> CancellationAgentState:
    logger.info(f"cancellation agent called — user: {state.get('user_id')}")

    input_messages = [
        m for m in state.get("messages", [])
        if getattr(m, "type", None) == "human" or (getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None))
    ]
    agent_state = {**state, "messages": input_messages}

    result = cancellation_react_agent.invoke(agent_state)

    cancel_draft = state.get("cancel_draft")
    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            import json
            try:
                content = json.loads(content)
            except Exception:
                pass
        if isinstance(content, dict) and content.get("status") == "draft":
            cancel_draft = content.get("cancel_draft")
            break

    return {
        **state,
        "messages":    result["messages"][len(input_messages):],
        "cancel_draft": cancel_draft
    }