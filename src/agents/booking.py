from langchain.agents import create_agent
from langgraph.graph import StateGraph, END
from src.agents.llm import get_llm
from src.graph.state import BookingAgentState
from src.tools.booking_tools import (
    get_theater_by_city,
    get_movies_by_city,
    get_movies_by_theaters,
    get_showtimes,
    book_tickets
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a movie ticket booking assistant.
You help users find movies, showtimes, and book tickets.

Tools available and when to use them:
- get_theater_by_city     : first step — get theaters in user's city
- get_movies_by_city      : first step — get movies in users's city and particular date
- get_movies_by_theaters  : second step — get movies showing today at those theaters
- get_showtimes           : third step — get show timings for a specific movie + theater
- book_tickets            : final step — book tickets ONLY after user confirms show + seats

Strict rules:
- ALWAYS follow the order: theaters → movies → showtimes → book
- NEVER skip get_theater_by_city — theater_id must come from tool result, never guessed
- NEVER skip get_movies_by_theaters — movie_id must come from tool result, never guessed
- NEVER call book_tickets unless the user has explicitly said "yes", "confirm", or "book it"
- if city is not in user message, use city from conversation context
- if user says "rebook last time" — extract show details from conversation history
- if seats are not chosen yet, tell user to use seat selection first
- after book_tickets returns a draft, tell user the booking summary and await confirmation
- always show: movie title, theater name, screen, date, time, seats, total price
"""

booking_react_agent = create_agent(
    get_llm(),
    tools=[
        get_theater_by_city,
        get_movies_by_city,
        get_movies_by_theaters,
        get_showtimes,
        book_tickets
    ],
    state_modifier=SYSTEM_PROMPT
)


def booking_node(state: BookingAgentState) -> BookingAgentState:
    logger.info(f"booking agent called — user: {state.get('user_id')}, city: {state.get('city')}")

    result = booking_react_agent.invoke(state)

    # extract booking_draft from tool messages if present
    booking_draft = state.get("booking_draft")
    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", None)
        if isinstance(content, dict) and content.get("status") == "draft":
            booking_draft = content.get("booking_draft")
            break

    return {
        **state,
        "messages":     result["messages"],
        "booking_draft": booking_draft
    }