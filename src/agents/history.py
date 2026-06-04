from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import HistoryAgentState
from src.tools.history_tools import (
    get_booking_history,
    get_booking_by_id,
    get_last_booking,
    get_bookings_by_status
)
from src.utils.logger import get_logger

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

history_react_agent = create_agent(
    get_llm(),
    tools=[
        get_booking_history,
        get_booking_by_id,
        get_last_booking,
        get_bookings_by_status
    ],
    state_modifier=SYSTEM_PROMPT
)


def history_node(state: HistoryAgentState) -> HistoryAgentState:
    logger.info(f"history agent called — user: {state.get('user_id')}")
    result = history_react_agent.invoke(state)
    return {**state, "messages": result["messages"]}