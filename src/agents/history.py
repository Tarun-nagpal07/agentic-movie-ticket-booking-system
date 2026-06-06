from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import HistoryAgentState
from src.tools.history_tools import make_history_tools
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages
logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a booking history assistant.
You help users view and understand their past bookings.

Tools available and when to use them:
- get_booking_history     : use for "show my bookings", "my history", "what have I booked"
- get_booking_by_id       : use when user mentions a specific booking ID
- get_last_booking        : use for "last booking", "most recent", "rebook same"
- get_bookings_by_status  : use for "show confirmed bookings" or "show cancelled bookings"

Strict rules:
- user_id always comes from state — never ask user for it
- for "how much have I spent" → get_booking_history, then sum all total_price fields
- for "rebook my last booking" → get_last_booking, then tell user to confirm
  and the booking agent will handle the actual booking
- always display in response:
    * movie title
    * theater name and screen
    * show date and time
    * seats and seat type
    * total price paid
    * booking status (confirmed / cancelled)
    * refund amount if cancelled
- sort display by most recent first
- if no history found → tell user they have no bookings yet, suggest browsing movies
"""


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

    result = react_agent.invoke(agent_state)
    return {**state, "messages": result["messages"][len(input_messages):]}