from langchain_core.messages import AIMessage
from src.agents.llm import get_llm
from src.config.settings import settings
from src.graph.state import BookingState
from src.schemas.planner import PlannerResponse
from src.config.constants import Intent
from src.utils.logger import get_logger
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
import json

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
If city is given to you that mean user is in that city , if user given explicitly city, then use that city.

Supported intents:
- search_movies     : user wants to find movies, theaters, or showtimes in a city
- get_showtimes     : user wants show timings for a specific movie or theater
- book_tickets      : user wants to book tickets for a show
- select_seats      : user wants to choose, can see full seat map or check specific seats,
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
    llm = get_llm(structure=True)
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

    # Keep only the last 10 messages to fit context window
    if len(formatted_msgs) > 10:
        formatted_msgs = formatted_msgs[-10:]

    try:
        response: PlannerResponse = structured_llm.invoke([
            {"role": "system", "content": system_with_context},
            *formatted_msgs
        ])
    except Exception as primary_exc:
        logger.warning(f"Primary planner structured output failed: {primary_exc}. Trying Hugging Face fallback...")
        if not settings.HF_TOKEN:
            logger.error("HF_TOKEN is not configured. Cannot run planner fallback.")
            raise primary_exc
        
        try:
            
            llama_endpoint = HuggingFaceEndpoint(
                repo_id=settings.FIRST_FALLBACK_LLM,
                huggingfacehub_api_token=settings.HF_TOKEN,
                max_new_tokens=512,
                temperature=0.01
            )
            llama_model = ChatHuggingFace(llm=llama_endpoint)
            
            fallback_prompt = f"""{system_with_context}
            
            You must classify the user message and return your response as a valid JSON object matching this schema:
            {{
                "intent": "string (one of: search_movies, get_showtimes, book_tickets, select_seats, recommend_movies, cancel_booking, get_history, policy_query, unknown)",
                "city": "string or null",
                "movie_title": "string or null"
            }}
            
            Return ONLY the raw JSON block. Do not write any explanations or conversational text.
            """
            
            raw_response = llama_model.invoke([
                {"role": "system", "content": fallback_prompt},
                *formatted_msgs
            ])
            
            content = raw_response.content.strip()
            if content.startswith("```"):
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()
                
            parsed = json.loads(content)
            response = PlannerResponse(
                intent=parsed.get("intent", "unknown"),
                city=parsed.get("city"),
                movie_title=parsed.get("movie_title")
            )
            logger.info("Successfully classified intent using Hugging Face fallback.")
        except Exception as fallback_exc:
            logger.error(f"Hugging Face planner fallback also failed: {fallback_exc}")
            raise primary_exc

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
            Politely inform the user that you can assist with movie ticket booking related questions, and gently steer them back.
            Directly reference what they asked in a natural way so they know you understood their input, but explain why you cannot help with it.
            Keep your response friendly, concise, and helpful.
            You can be GenZ, and handle the situation.
            """
        refusal_response = llm.invoke([
            {"role": "system", "content": refusal_prompt}
        ])
        res["messages"] = [AIMessage(content=refusal_response.content)]

    return res