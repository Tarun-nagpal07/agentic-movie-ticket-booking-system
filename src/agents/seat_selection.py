from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import SeatAgentState
from src.tools.seat_tools import (
    get_seat_map,
    get_seats_types_available,
    get_seats_available
)
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages
logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a seat selection assistant for movie ticket booking.
Your job is to show REAL seat availability from the theater system.

Tools and when to use them:
- get_seat_map              : call first — gets the full real seat layout for the show
- get_seats_types_available : call to filter by row type using ROW LETTERS not type names
- get_seats_available       : call to check if specific seat IDs are available

CRITICAL rules — read carefully:
- NEVER mention or suggest any seat that was not returned by a tool
- NEVER say a seat is available unless the tool returned it as "available"
- NEVER say a seat type exists in a theater unless the tool confirmed it
- if get_seat_map returns no "E" row — there are NO recliner seats, tell user clearly
- seat_types in tool results map ROW LETTERS to type names:
    example: {"A": "standard", "B": "standard", "D": "premium", "E": "recliner"}
    its just an example, may vary according to the theaters and screens.
- when calling get_seats_types_available, pass ROW LETTERS not type names:
    for recliner → check seat_types map → find which row is "recliner" → pass that row letter
    example: user wants recliner → seat_types shows E=recliner → pass ["E"]
- ALWAYS call get_seat_map first to know which rows exist before filtering

Workflow for every seat request:
1. call get_seat_map(theater_id, movie_id, show_id)
2. read seat_types from result to understand row → type mapping
3. if user wants a type (recliner/premium/standard):
   → find the row letter(s) for that type from seat_types
   → call get_seats_types_available with those row letters
4. if user wants specific seats (e.g. E5, E6):
   → call get_seats_available to verify
5. show ONLY what tools returned — never add or invent seats

Response format:
- group seats by row
- show seat type for each row
- show count of available seats per row
- highlight if a requested type doesn't exist in this theater
"""


seat_react_agent = create_agent(
    get_llm(),
    tools=[
        get_seat_map,
        get_seats_types_available,
        get_seats_available
    ],
    system_prompt=SYSTEM_PROMPT,
    middleware=[trim_messages]
)


def seat_selection_node(state: SeatAgentState) -> SeatAgentState:
    logger.info(f"seat selection agent called — user: {state.get('user_id')}")

    input_messages = [
        m for m in state.get("messages", [])
        if getattr(m, "type", None) == "human" or (getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None))
    ]
    agent_state = {**state, "messages": input_messages}

    result = seat_react_agent.invoke(agent_state)

    seat_map       = state.get("seat_map")
    available_seats = state.get("available_seats")

    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", None)
        if isinstance(content, dict):
            if "seats" in content:
                seat_map = content.get("seats")
            if "available_seats" in content:
                available_seats = content.get("available_seats")

    return {
        **state,
        "messages":       result["messages"][len(input_messages):],
        "seat_map":       seat_map,
        "available_seats": available_seats
    }