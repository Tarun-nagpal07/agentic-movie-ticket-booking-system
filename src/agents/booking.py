from langchain.agents import create_agent
from langgraph.graph import StateGraph, END
from src.agents.llm import get_llm
from src.graph.state import BookingAgentState
from src.tools.booking_tools import (
    get_theater_by_city,
    get_movies_by_theaters,
    get_showtimes,
    book_tickets
)
from src.tools.seat_tools import (
    get_available_seats,
    recommend_seats
)
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages
from langchain_core.messages import SystemMessage
from src.utils.id_cleaner import remove_raw_ids
from src.utils.date_utils import get_today
from datetime import datetime, timedelta
from langchain_core.messages import AIMessage
logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a movie ticket booking assistant.
You help users find movies, showtimes, and book tickets.

[CRITICAL RULE: CONCEAL ALL DATABASE IDS]
- NEVER display, print, or mention raw database IDs (such as theater_id, movie_id, show_id, e.g. 't1', 'm2', 's101') in your final text responses or listings shown to the user.
- If a tool returns IDs, keep them hidden in the background for tool calling purposes. ONLY present the readable theater names, movie titles, show times, and addresses to the user.
- DO NOT print "(Theater ID: ...)" or "(Movie ID: ...)" or "(ID: ...)" in your output.

Tools available and when to use them:
- get_theater_by_city     : first step — get theaters in user's city
- get_movies_by_theaters  : second step — get movies showing on the selected date at those theaters. Supports optional `movie_name` parameter for fuzzy filtering.
- get_showtimes           : third step — get show timings for a specific movie + theater on the selected date. Supports optional `movie_name` parameter for fuzzy resolution.
- get_available_seats     : fourth step — show user real available seats for a chosen show. Call when user asks to see seats, seat map, or availability. Optionally filters by `seat_type` ("standard", "premium", "recliner").
- recommend_seats         : alternative to get_available_seats — recommend best consecutive seats based on user history or explicit seat type request. Call when user says "pick best seats", "recommend seats", "book X tickets".
- book_tickets            : final step — book tickets ONLY after user confirms show + seats.

Strict rules:
- NEVER guess any IDs (theater_id, movie_id, show_id), theater names, movie titles, show times, available seats, or dates. If any value is missing and not provided in the "Current booking context" or user messages, you MUST ask the user to specify it instead of guessing.
- ALWAYS follow the order: theaters → movies → showtimes → seats/recommend_seats → book
- ALWAYS check the "Current booking context" system message first. If `theater_id` and/or `movie_id` are already present in the context, you MUST use them directly. In this case, you can skip get_theater_by_city and/or get_movies_by_theaters and proceed directly to get_showtimes or seats/recommend_seats.
- Only call get_theater_by_city if no theater_id/theater_name is present in the context or if the user asks to change the theater.
- Only call get_movies_by_theaters if no movie_id/movie_title is present in the context or if the user asks to change the movie.
- NEVER call book_tickets unless the user has explicitly said "yes", "confirm", "book them", or "book it".
- If the user's city is not known (neither explicitly mentioned in the messages nor present in the "User's current city" system context), you MUST ask the user which city they are in. DO NOT guess the city, and DO NOT call get_theater_by_city without knowing the city.
- If the user's city is known, use that city for all theater and movie searches.
- ALWAYS use the selected booking date provided in the system messages when calling tools. DO NOT guess any date. If the user doesn't specify a date, it defaults to today.
- if user says "rebook last time" — extract show details from conversation history.
- NEVER book tickets without showing the available seats (via get_available_seats) or getting recommended seats (via recommend_seats) first.
- If the user has not chosen seats but wants to book, or asks to book tickets (e.g. "book 2 tickets"), use recommend_seats to find the best available seats and present them to the user for confirmation.
- After book_tickets returns a draft, tell user the booking summary and await confirmation.
- Always show: movie title, theater name, screen, date, time, seats, total price.
"""

booking_react_agent = create_agent(
    get_llm(),
    tools=[
        get_theater_by_city,
        get_movies_by_theaters,
        get_showtimes,
        get_available_seats,
        recommend_seats,
        book_tickets
    ],
    system_prompt=SYSTEM_PROMPT,
    middleware=[trim_messages],
    debug=True
)



def booking_node(state: BookingAgentState) -> BookingAgentState:
    logger.info(f"booking agent called — user: {state.get('user_id')}, city: {state.get('city')}, date: {state.get('date')}")

    today_str = get_today()
    date = state.get("date") or today_str

    today_dt = datetime.strptime(today_str, "%Y-%m-%d")
    max_date_dt = today_dt + timedelta(days=3)
    max_date_str = max_date_dt.strftime("%Y-%m-%d")

    if date < today_str or date > max_date_str:
        msg = AIMessage(content="Showtimes are not available for this date. You can only book tickets up to 4 days from now.")
        return {
            **state,
            "messages": [msg]
        }

    from src.utils.id_cleaner import (
        extract_entities_from_text,
        extract_ids_from_tool_calls,
        resolve_movie_id,
        get_movie_title_by_id,
        get_theater_name_by_id,
        resolve_implicit_theater,
        resolve_implicit_show,
        validate_and_clear_theater_id,
        validate_and_clear_show_id
    )

    # 1. Extract entities from the latest user message
    text_updates = {}
    latest_human_msg = next((m.content for m in reversed(state.get("messages", [])) if getattr(m, "type", None) == "human"), "")
    if latest_human_msg:
        text_updates = extract_entities_from_text(latest_human_msg)

    city = state.get("city")

    # 2. Track current context
    current_theater_id = text_updates.get("theater_id") or state.get("theater_id")
    current_theater_name = text_updates.get("theater_name") or state.get("theater_name")

    # Ensure theater_id and theater_name match
    if current_theater_id:
        expected_name = get_theater_name_by_id(current_theater_id)
        if not expected_name or (current_theater_name and expected_name.lower() != current_theater_name.lower()):
            current_theater_id = None
            current_theater_name = None

    # Validate theater against active city
    current_theater_id, validated_name = validate_and_clear_theater_id(city, current_theater_id)
    current_theater_name = text_updates.get("theater_name") or validated_name or state.get("theater_name")
    if not current_theater_id:
        current_theater_name = None

    current_movie_id = text_updates.get("movie_id") or state.get("movie_id")
    current_movie_title = text_updates.get("movie_title") or state.get("movie_title")

    # Ensure movie_id and movie_title match
    if current_movie_id:
        expected_title = get_movie_title_by_id(current_movie_id)
        if not expected_title or (current_movie_title and expected_title.lower() != current_movie_title.lower()):
            current_movie_id = None
            
    # Validate show_id against active theater, movie, and date
    current_show_id = validate_and_clear_show_id(current_theater_id, current_movie_id, date, state.get("show_id"))

    if current_movie_title and not current_movie_id:
        resolved_mid = resolve_movie_id(current_movie_title)
        if resolved_mid != current_movie_title:
            current_movie_id = resolved_mid
            current_movie_title = get_movie_title_by_id(resolved_mid) or current_movie_title

    # 2.5 Resolve implicit theater if movie is selected but theater is not, and exactly one theater is showing it
    if current_movie_id and not current_theater_id:
        implicit_t = resolve_implicit_theater(city, current_movie_id, date)
        if implicit_t:
            current_theater_id = implicit_t.get("theater_id")
            current_theater_name = implicit_t.get("theater_name")

    # 2.6 Resolve implicit show_id if movie and theater are known
    if current_movie_id and current_theater_id and not current_show_id:
        current_show_id = resolve_implicit_show(current_theater_id, current_movie_id, date, latest_human_msg)

    input_messages = [
        m for m in state.get("messages", [])
        if getattr(m, "type", None) == "human" or (getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None))
    ]
    
    # Inject current date and selected date context so the agent has full time context
    input_messages = [SystemMessage(content=f"Today's date: {today_str}\nSelected booking date: {date}")] + input_messages

    # 3. Inject context (IDs and Names) so LLM knows selected theater/movie/show
    context_parts = []
    if current_theater_id and current_theater_name:
        context_parts.append(f"Selected Theater: {current_theater_name} (ID: {current_theater_id})")
    elif current_theater_id:
        context_parts.append(f"Selected Theater ID: {current_theater_id}")
    elif current_theater_name:
        context_parts.append(f"Selected Theater Name: {current_theater_name}")

    if current_movie_id and current_movie_title:
        context_parts.append(f"Selected Movie: {current_movie_title} (ID: {current_movie_id})")
    elif current_movie_id:
        context_parts.append(f"Selected Movie ID: {current_movie_id}")
    elif current_movie_title:
        context_parts.append(f"Selected Movie Title: {current_movie_title}")

    if current_show_id:
        context_parts.append(f"Selected Show ID: {current_show_id}")

    if context_parts:
        context_str = "\n".join(context_parts)
        input_messages = [SystemMessage(content=f"Current booking context:\n{context_str}")] + input_messages

    city = state.get("city")
    if city:
        input_messages = [SystemMessage(content=f"User's current city: {city}")] + input_messages

    agent_state = {**state, "messages": input_messages}

    result = booking_react_agent.invoke(agent_state)

    # extract booking_draft from tool messages if present
    booking_draft = state.get("booking_draft")
    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            import json
            try:
                content = json.loads(content)
            except Exception:
                pass
        if isinstance(content, dict) and content.get("status") == "draft":
            booking_draft = content.get("booking_draft")
            break

    # 4. Extract updated IDs from tool calls made in this turn
    tool_updates = extract_ids_from_tool_calls(result["messages"])

    final_theater_id = tool_updates["theater_id"] if "theater_id" in tool_updates else current_theater_id
    final_theater_name = tool_updates["theater_name"] if "theater_name" in tool_updates else current_theater_name
    final_movie_id = tool_updates["movie_id"] if "movie_id" in tool_updates else current_movie_id
    final_movie_title = tool_updates["movie_title"] if "movie_title" in tool_updates else current_movie_title
    final_show_id = tool_updates["show_id"] if "show_id" in tool_updates else current_show_id

    returned_messages = result["messages"][len(input_messages):]
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
        "messages":     cleaned_messages,
        "booking_draft": booking_draft,
        "theater_id":   final_theater_id,
        "theater_name": final_theater_name,
        "movie_id":     final_movie_id,
        "movie_title":  final_movie_title,
        "show_id":      final_show_id,
    }