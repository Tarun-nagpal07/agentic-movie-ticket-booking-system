from src.agents.llm import get_llm
from src.graph.state import BookingState
from src.schemas.planner import PlannerResponse
from src.config.constants import Intent
from src.utils.logger import get_logger

logger = get_logger(__name__)

INTENT_TO_AGENT = {
    Intent.SEARCH_MOVIES:    "booking",
    Intent.GET_SHOWTIMES:    "booking",
    Intent.BOOK_TICKETS:     "booking",
    Intent.SELECT_SEATS:     "seat",
    Intent.RECOMMEND_MOVIES: "recommend",
    Intent.CANCEL_BOOKING:   "cancellation",
    Intent.GET_HISTORY:      "history",
    Intent.POLICY_QUERY:     "policy",
    Intent.UNKNOWN:          "unknown",
}

SYSTEM_PROMPT = """
You are the intent classifier for a movie ticket booking assistant.
Your ONLY job is to read the user message and classify the intent.
Do NOT answer the user. Do NOT call any tools. ONLY return structured output.

Supported intents:
- search_movies     : user wants to find movies, theaters, or showtimes in a city
- get_showtimes     : user wants show timings for a specific movie or theater
- book_tickets      : user wants to book tickets for a show
- select_seats      : user wants to choose or check specific seats
- recommend_movies  : user wants movie suggestions based on preferences or history
- cancel_booking    : user wants to cancel an existing booking
- get_history       : user wants to see past bookings or spending
- policy_query      : user asks about cancellation rules, refunds, policies, FAQs
- unknown           : cannot determine intent from message

Rules:
- if city is not mentioned but user memory has a city → use memory city
- if movie_title is partial (e.g. "that sci-fi one") → leave it None, agent will ask
- if date is not mentioned → leave it None, tools default to today
- always classify to the most specific intent possible
- "rebook" or "same as last time" → book_tickets intent
- "what can I watch" or "suggest" → recommend_movies intent
- "where can I watch X" → search_movies intent
"""

def planner_node(state: BookingState) -> BookingState:
    llm = get_llm()
    structured_llm = llm.with_structured_output(PlannerResponse)

    memory  = state.get("memory", {})
    messages = state.get("messages", [])

    system_with_context = f"""{SYSTEM_PROMPT}

                            User context from memory:
                            - city: {memory.get("city", "unknown")}
                            - favorite genres: {memory.get("favorite_genres", [])}
                            - language preference: {memory.get("language_pref", "unknown")}
                            - past bookings count: {len(memory.get("booking_history", []))}
                            """

    response: PlannerResponse = structured_llm.invoke([
        {"role": "system", "content": system_with_context},
        *[{"role": m["role"], "content": m["content"]}
          for m in messages
          if isinstance(m.get("content"), str)]
    ])

    next_agent = INTENT_TO_AGENT.get(response.intent, "unknown")

    logger.info(f"planner → intent: {response.intent}, next_agent: {next_agent}, city: {response.city}")

    return {
        **state,
        "intent":      response.intent,
        "next_agent":  next_agent,
        "city":        response.city or memory.get("city"),
        "movie_title": response.movie_title,
        "date":        '2025-06-01',
    }