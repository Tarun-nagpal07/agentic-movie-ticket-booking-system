from langchain.agents import create_agent
import json
from src.agents.llm import get_llm
from src.graph.state import CancellationAgentState
from src.tools.cancellation_tools import make_cancellation_tools
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages, extract_new_messages
from src.utils.id_cleaner import remove_raw_ids
from langchain_core.messages import AIMessage, SystemMessage
from src.prompts.cancellation import SYSTEM_PROMPT

logger = get_logger(__name__)



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