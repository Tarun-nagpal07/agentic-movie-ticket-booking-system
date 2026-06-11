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
    Intent.SELECT_SEATS:     "booking",
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
- you can book upto 4 days from now.
- if movie_title is partial (e.g. "that sci-fi one") → leave it None, agent will ask
- if date is not mentioned or if user asks for shows "today", "tonight", or "now" → leave the date field as null (None). Do not resolve it to a specific date string yourself.
- if a specific relative date like "tomorrow", "day after tomorrow", "in 3 days", "in 4 days" or an absolute date is mentioned, extract it normalized (e.g. "tomorrow", "day after tomorrow"). If they misspelled it, extract the closest standard relative date token.
- always classify to the most specific intent possible
- "rebook" or "same as last time" → book_tickets intent
- "what can I watch" or "suggest" → recommend_movies intent
- "where can I watch X" → search_movies intent
"""

def resolve_date_string(date_str: str | None) -> str:
    from src.utils.date_utils import get_today
    from datetime import datetime, timedelta
    import re
    
    today_str = get_today()
    if not date_str:
        return today_str
        
    date_str_clean = date_str.lower().strip()
    if date_str_clean in ("none", "null", "undefined", ""):
        return today_str
        
    base_dt = datetime.strptime(today_str, "%Y-%m-%d")
    
    # Check for relative keywords (more specific keywords checked first)
    if "day after" in date_str_clean:
        return (base_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    elif re.search(r"\b(t[om]{2,4}o?r{1,2}[ow]*|tmw)\b", date_str_clean) or "tomorrow" in date_str_clean or "tomoorow" in date_str_clean:
        return (base_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    elif re.search(r"\b(tod[aeiouy]{1,3}|tonig[ht]*|tonite)\b", date_str_clean) or "today" in date_str_clean or "tonight" in date_str_clean:
        return today_str
    elif re.search(r"\b(3|three)\s+day", date_str_clean) or "in 3" in date_str_clean:
        return (base_dt + timedelta(days=3)).strftime("%Y-%m-%d")
    elif re.search(r"\b(4|four)\s+day", date_str_clean) or "in 4" in date_str_clean:
        return (base_dt + timedelta(days=4)).strftime("%Y-%m-%d")
        
    # Match YYYY-MM-DD
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", date_str_clean)
    if match:
        return match.group(0)
        
    # Match MM-DD or MM/DD (assuming current base year)
    match_short = re.search(r"\b(\d{1,2})[-/](\d{1,2})\b", date_str_clean)
    if match_short:
        month = int(match_short.group(1))
        day = int(match_short.group(2))
        return f"{base_dt.year}-{month:02d}-{day:02d}"
        
    # Match date patterns like "June 2", "2nd June", "June 2nd", "Jun 2"
    months_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
    }
    
    for mname, mnum in months_map.items():
        if mname in date_str_clean:
            day_match = re.search(r"\b(\d{1,2})(st|nd|rd|th)?\b", date_str_clean.replace(mname, ""))
            if day_match:
                day = int(day_match.group(1))
                return f"{base_dt.year}-{mnum:02d}-{day:02d}"
                
    return date_str

def planner_node(state: BookingState) -> BookingState:
    llm = get_llm(structure=True)
    structured_llm = llm.with_structured_output(PlannerResponse)

    memory  = state.get("memory", {})
    messages = state.get("messages", [])

    from src.utils.date_utils import get_today
    system_with_context = f"""{SYSTEM_PROMPT}

                            Current date: {get_today()}

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

    # Keep only the last 15 messages to fit context window
    if len(formatted_msgs) > 15:
        formatted_msgs = formatted_msgs[-15:]

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
                repo_id=settings.SECOND_FALLBACK_LLM,
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
        "city":        response.city or state.get("city") or memory.get("city"),
        "movie_title": response.movie_title or state.get("movie_title"),
        "date":        resolve_date_string(response.date or state.get("date")),
        "redirect_to_planner": None,
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