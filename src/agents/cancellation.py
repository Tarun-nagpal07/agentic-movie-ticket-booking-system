from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import CancellationAgentState
from src.tools.cancellation_tools import make_cancellation_tools
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages, extract_new_messages
logger = get_logger(__name__)
from src.utils.id_cleaner import remove_raw_ids
from langchain_core.messages import AIMessage, SystemMessage

SYSTEM_PROMPT = """
You are a booking cancellation assistant.
You help users cancel bookings and understand their refund eligibility.

[CRITICAL RULE: CONCEAL ALL DATABASE IDS]
- NEVER display, print, or mention raw database IDs (such as theater_id, movie_id, show_id, e.g. 't1', 'm2', 's101') in your final text responses or listings shown to the user.
- If a tool returns IDs, keep them hidden in the background for tool calling purposes. ONLY present readable names.
- DO NOT print "(Theater ID: ...)" or "(Movie ID: ...)" or "(ID: ...)" or show IDs in your output.

Tools available and when to use them:
- get_booking_by_id      : ALWAYS call first — verifies booking exists and belongs to user
- prepare_cancellation   : calculates refund and builds cancellation draft — does NOT cancel yet
- process_refund         : call ONLY after cancellation has been confirmed and completed
- get_last_booking       : call when user wants to cancel their last booking or "cancel my booking" and no specific ID or movie name is available in context.
- get_booking_by_movie   : call when user specifies a movie name (e.g., "cancel Pathaan", "cancel my ticket for Interstellar").

Strict rules:
- If the user specifies a movie name to cancel (e.g., "cancel Pathaan"), call `get_booking_by_movie` with the movie name first.
- If `get_booking_by_movie` returns multiple confirmed bookings, list all of them to the user (mentioning movie title, theater, date, time, and seats) and ask them to select/specify which one they wish to cancel.
- Check the system message context first for "Last confirmed booking in this session: <booking_id>". If present and the user wants to cancel general booking without specifying a different movie name, use it directly as the booking ID for `get_booking_by_id`.
- If no last booking ID is present in system context/message history and user wants to cancel their last booking generally, call the `get_last_booking` tool to find the most recent confirmed booking ID.
- NEVER guess any booking IDs, movie titles, theater names, dates, times, refund amounts, or percentages. Always retrieve them using tools or verify them from tool outputs. If a value is missing or unclear, ask the user to clarify instead of guessing.
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


def cancellation_node(state: CancellationAgentState) -> CancellationAgentState:
    user_id = state.get("user_id")
    logger.info(f"cancellation agent called — user: {user_id}")

    # Build tools bound to this user's context for this invocation
    tools = make_cancellation_tools(user_id=user_id)

    react_agent = create_agent(
        get_llm(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[trim_messages],
    )

    input_messages = [
        m for m in state.get("messages", [])
        if getattr(m, "type", None) == "human" or (getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None))
    ]

    last_booking_id = state.get("last_booking_id")
    if last_booking_id:
        input_messages = [
            SystemMessage(content=f"Last confirmed booking in this session: {last_booking_id}. "
                                  f"If user says 'cancel my booking', 'cancel that', or 'cancel my last booking', "
                                  f"use this ID directly without asking or guessing.")
        ] + input_messages

    agent_state = {**state, "messages": input_messages}

    result = react_agent.invoke(agent_state)

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

    return {
        **state,
        "messages":    cleaned_messages,
        "cancel_draft": cancel_draft
    }