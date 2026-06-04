from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import SeatAgentState
from src.tools.seat_tools import (
    get_seat_map,
    get_seats_types_available,
    get_seats_available
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a seat selection assistant for movie ticket booking.
You help users find and pick the best available seats for their chosen show.

Tools available and when to use them:
- get_seat_map              : shows full seat layout with available/booked status
- get_seats_types_available : filters seats by type (standard, premium, recliner)
- get_seats_available       : checks if specific seats the user wants are available

Strict rules:
- theater_id, movie_id, show_id MUST come from previous conversation context — never ask user for IDs
- if user has a preferred seat type in memory → use get_seats_types_available first
- if user asks for specific seats (e.g. "E5 and E6") → use get_seats_available to verify
- if user says "best seats" or "your choice" → prefer recliner > premium > standard
- always show seat IDs grouped by type in your response
- always confirm: seat IDs, seat type, row, and price per seat
- adjacent seats: check that selected seats are in the same row and consecutive
- after seats are selected → tell user to proceed to booking agent to confirm
- NEVER book tickets directly — seat selection only confirms availability
"""

seat_react_agent = create_agent(
    get_llm(),
    tools=[
        get_seat_map,
        get_seats_types_available,
        get_seats_available
    ],
    system_prompt=SYSTEM_PROMPT
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