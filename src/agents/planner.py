from langchain_core.messages import AIMessage
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

    # LangGraph messages are objects (HumanMessage/AIMessage) with .type and .content
    formatted_msgs = []
    for m in messages:
        content = getattr(m, "content", None)
        msg_type = getattr(m, "type", None)
        if msg_type in ("human", "ai") and isinstance(content, str):
            role = "user" if msg_type == "human" else "assistant"
            formatted_msgs.append({"role": role, "content": content})

    response: PlannerResponse = structured_llm.invoke([
        {"role": "system", "content": system_with_context},
        *formatted_msgs
    ])

    next_agent = INTENT_TO_AGENT.get(response.intent, "unknown")

    logger.info(f"planner → intent: {response.intent}, next_agent: {next_agent}, city: {response.city}")

    res = {
        "intent":      response.intent,
        "next_agent":  next_agent,
        "city":        response.city or memory.get("city"),
        "movie_title": response.movie_title,
        "date":        '2025-06-01',
    }

    if response.intent == Intent.UNKNOWN or next_agent == "unknown":
        # Extract the last human message content for context
        user_message_content = ""
        for m in reversed(messages):
            if getattr(m, "type", None) == "human":
                user_message_content = getattr(m, "content", "")
                break

        refusal_prompt = f"""You are a helpful and polite movie ticket booking assistant.
The user asked: "{user_message_content}"
This request is off-topic or irrelevant to movie booking, showtimes, seats, ticket cancellations, or movie-theater policies.
Politely inform the user that you can only assist with movie ticket booking related questions, and gently steer them back.
Directly reference what they asked in a natural way so they know you understood their input, but explain why you cannot help with it.
Keep your response friendly, concise, and helpful.
"""
        refusal_response = llm.invoke([
            {"role": "system", "content": refusal_prompt}
        ])
        res["messages"] = [AIMessage(content=refusal_response.content)]

    return res