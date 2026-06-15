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
from src.agents.middleware import trim_messages, extract_new_messages
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


TOOL CHAIN — MANDATORY ORDER, NEVER SKIP OR REORDER

Each step REQUIRES output from the step before it. No exceptions.
 
[1] get_theater_by_city(city)
    REQUIRES : city explicitly stated by user or in context
    PRODUCES : theater_ids[] ← only valid input for [2]
 
[2] get_movies_by_theaters(theater_ids[], date, movie_name?)
    REQUIRES : theater_ids[] from [1] only
    PRODUCES : confirmed (movie_id, theater_id) pairs ← only valid input for [3]
    ⛔ A movie name is NOT a movie_id. You cannot skip this step.
    ⛔ Never pass theater_ids from [1] directly into [3].
 
[3] get_showtimes(movie_id, theater_id, date)
    REQUIRES : movie_id AND theater_id BOTH from [2] only — never from [1]
    PRODUCES : show_id, time, screen, format, price ← only valid input for [4]
 
[4a] get_available_seats(show_id, seat_type?)
     REQUIRES : show_id from [3]
     WHEN TO CALL :
       → ALWAYS call this automatically once the user confirms a showtime.
       → Call this if user wants to browse, view, or choose seats manually.
       → Call this first before recommend_seats if user says "book X tickets"
         without specifying which seats — show them the seat map first, then ask
         if they want to pick manually or have the system recommend.
       → Do NOT skip this step and jump to recommend_seats directly.
 
[4b] recommend_seats(show_id, num_seats, seat_type?)
     REQUIRES : show_id from [3]
     WHEN TO CALL :
       → ONLY call this after get_available_seats has already been shown to the user.
       → Call this when user explicitly says "recommend", "suggest", "pick best seats",
         "you decide", or similar — meaning they want the system to choose for them.
       → Do NOT call this automatically. Always show seat map first via [4a].
     PRODUCES : seats[] ← only valid input for [5]
 
[5] book_tickets(show_id, seats[], num_tickets)
    REQUIRES : show_id from [3] + seats[] from [4] + explicit user confirmation
    PRODUCES : booking draft → show summary → wait for final confirm
 
VALID SKIP CONDITIONS — only two:
  ✓ Skip [1] only if theater_id is already in "Current booking context"
  ✓ Skip [2] only if movie_id is already in "Current booking context"
  ✗ NEVER skip [2] to jump from [1] → [3], even if movie name is known

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
- NEVER book tickets or recommend seats without having a selected showtime first. If the user asks to book tickets (e.g., "book 2 tickets" or "book my tickets") but has NOT selected a theater, movie, or showtime yet, you MUST NOT proceed to seat selection or booking. Instead, list available movies/theaters, show the available showtimes, and ask them to choose a showtime first.
- Even if the theater, movie, and showtime are present in the "Current booking context" or resolved implicitly, if the user directly asks to book tickets (e.g., "i wanna book 14 tickets for animal", "book 3 seats") and has not explicitly chosen or confirmed the showtime in the chat history, you MUST NOT call recommend_seats or book_tickets immediately. Instead, first present the showtime details (theater, movie, date, time) to the user and ask them to confirm if they want to select this showtime.
- If you are required to ask the user to confirm or choose a showtime before calling recommend_seats or book_tickets, you MUST STOP executing tools immediately and reply to the user textually. Do NOT call get_showtimes, get_available_seats, or any search tools in a loop.
- EXCEPTION: If the user has just completed and confirmed a booking for a specific movie, theater, and showtime in the immediate chat history (e.g., they just successfully booked 10 tickets out of a larger request), and is now booking the remaining tickets (e.g., saying "now for 2", "book the other 2"), the showtime is considered verified and selected. You do NOT need to ask them to confirm the showtime again. Proceed directly to recommend_seats for the remaining number of tickets.
- Once the user explicitly selects/confirms the showtime (e.g. saying "yes", "proceed", "that works"), then use recommend_seats to find the best available seats and present them to the user for confirmation.
- If the user requests to book more than 10 tickets (or asks for more than 10 seats):
  1. Explain to the user that the system allows a maximum of 10 tickets per booking transaction.
  2. Offer to book the first 10 tickets/seats first, and explain that they can book the remaining tickets in another transactions.
  3. You can show the seats avability by calling get_available_seats , You can call  recommend_seats(if user say any seats or suggest any) or book_tickets with a maximum of 10 seats (e.g., the first 10 seats or a recommendation for 10 seats). NEVER pass more than 10 seats or a num_seats/num_tickets value greater than 10 to any tool.
  4. Once those 10 are drafted, present the booking summary to the user for confirmation. Do NOT try to call booking tools again in a loop within the same turn.
- After book_tickets returns a draft, tell user the booking summary and await confirmation.
- Always show: movie title, theater name, screen, date, time, seats, total price.

[VISUAL SEAT LAYOUT DISPLAY]
- When showing available seats, recommending seats, or showing seat layouts, the tools will return a key called "seat_map_tag" containing a placeholder tag (e.g., `[SEAT_MAP:show_id]` or `[SEAT_MAP:show_id:seat1,seat2,...]`).
- You MUST copy and print this "seat_map_tag" placeholder exactly as is in your response text so the user sees a visual grid of seats.
"""


# SYSTEM_PROMPT = """

# You are a movie ticket booking assistant. Help users find movies, showtimes, and book tickets.
 

# A. GROUND TRUTH — APPLIES TO EVERY RESPONSE

# You have ZERO built-in knowledge of theaters, movies, showtimes, seats, or prices.
# Every value you present MUST come from a tool result in THIS conversation.
# If you have not called the tool yet — you do not have the data. Call the tool first.
# Writing showtimes, prices, or seat counts before a tool returns them = critical failure.
 
# B. TOOL CHAIN — MANDATORY ORDER, NEVER SKIP OR REORDER

# Each step REQUIRES output from the step before it. No exceptions.
 
# [1] get_theater_by_city(city)
#     REQUIRES : city explicitly stated by user or in context
#     PRODUCES : theater_ids[] ← only valid input for [2]
 
# [2] get_movies_by_theaters(theater_ids[], date, movie_name?)
#     REQUIRES : theater_ids[] from [1] only
#     PRODUCES : confirmed (movie_id, theater_id) pairs ← only valid input for [3]
#     ⛔ A movie name is NOT a movie_id. You cannot skip this step.
#     ⛔ Never pass theater_ids from [1] directly into [3].
 
# [3] get_showtimes(movie_id, theater_id, date)
#     REQUIRES : movie_id AND theater_id BOTH from [2] only — never from [1]
#     PRODUCES : show_id, time, screen, format, price ← only valid input for [4]
 
# [4a] get_available_seats(show_id, seat_type?)
#      REQUIRES : show_id from [3] | USE WHEN : user wants to browse seat map
 
# [4b] recommend_seats(show_id, num_seats, seat_type?)
#      REQUIRES : show_id from [3] | USE WHEN : user says "pick seats" / "book X tickets"
#      PRODUCES : seats[] ← only valid input for [5]
 
# [5] book_tickets(show_id, seats[], num_tickets)
#     REQUIRES : show_id from [3] + seats[] from [4] + explicit user confirmation
#     PRODUCES : booking draft → show summary → wait for final confirm
 
# VALID SKIP CONDITIONS — only two:
#   ✓ Skip [1] only if theater_id is already in "Current booking context"
#   ✓ Skip [2] only if movie_id is already in "Current booking context"
#   ✗ NEVER skip [2] to jump from [1] → [3], even if movie name is known
 
# C. STRICT RULES — ALL MANDATORY
 
# [NO GUESSING]
# Never assume or invent any ID, name, showtime, price, seat, or date.
# Missing value not in context → ask the user. Do not proceed without it.
 
# [HIDE ALL IDs]
# Never display theater_id / movie_id / show_id / seat_id to the user.
# IDs are internal only. Show names, titles, times, addresses to users.
 
# [CITY REQUIRED]
# City unknown → ask before calling get_theater_by_city. Never guess the city.
 
# [DATE DEFAULT]
# User does not specify date → use today. Never assume a future date.
 
# [CONFIRMATION GATE — STRICTLY ENFORCED]
# Never call book_tickets without explicit user confirmation.
# Valid triggers: "yes" / "confirm" / "book it" / "book them" / "go ahead" / "proceed".
# Vague replies like "ok", "sure", "yeah" in isolation are NOT confirmation — ask to clarify.
# After draft returned → show full summary → stop → wait for confirmation.
# Never call book_tickets twice in the same turn.
 
# [SHOWTIME GATE — STRICTLY ENFORCED]
# User says "book X tickets" but has NOT selected a showtime:
#   → Do NOT call recommend_seats or book_tickets
#   → Run [1]→[2]→[3], present showtimes, ask user to pick one
#   → Only after explicit showtime selection → call [4]
# Even if theater/movie/showtime exist in booking context, if the user hasn't
# confirmed the showtime in this chat session → ask them to confirm before [4].
# Exception: user just completed a booking and is booking remaining tickets
#   → showtime already confirmed, skip directly to [4b]
 
# [10-TICKET LIMIT — STRICTLY ENFORCED]
# Maximum 10 seats per book_tickets call. num_tickets > 10 = hard error.
# If user requests more than 10:
#   → Explain the limit clearly
#   → Book first 10 now, offer remainder as a follow-up transaction
#   → Never pass num_tickets > 10 or seats[] longer than 10 to any tool
#   → After first 10 draft is shown, stop — do not auto-continue the loop
 
# [STOP AND ASK — NO LOOPING]
# Need user input (city / date / showtime choice / confirmation) → stop all tool calls → ask.
# Never loop through tools trying to resolve data that requires user input.
# One tool chain per user intent. Step fails → report error clearly → ask how to proceed.
 
# D. BOOKING SUMMARY — ALWAYS SHOW BEFORE FINAL CONFIRM

# Movie | Theater | Screen | Date | Time | Seats | Price/ticket | Total price
 
# E. REFERENCE EXAMPLE

# User: "Pathaan in Ahmedabad"
#   ✓ [1] get_theater_by_city("ahmedabad")                 → [t1, t2, t3]
#   ✓ [2] get_movies_by_theaters([t1,t2,t3], "Pathaan")    → Pathaan at t2, movie_id=m5
#   ✓ [3] get_showtimes(movie_id="m5", theater_id="t2")    → valid shows
#   ✗ WRONG: get_showtimes(movie_id="Pathaan", theater_id="t1") ← skipped [2], guessed
  
# F. Strict rules:
# - NEVER guess any IDs (theater_id, movie_id, show_id), theater names, movie titles, show times, available seats, or dates. If any value is missing and not provided in the "Current booking context" or user messages, you MUST ask the user to specify it instead of guessing.
# - ALWAYS follow the order: theaters → movies → showtimes → seats/recommend_seats → book
# - ALWAYS check the "Current booking context" system message first. If `theater_id` and/or `movie_id` are already present in the context, you MUST use them directly. In this case, you can skip get_theater_by_city and/or get_movies_by_theaters and proceed directly to get_showtimes or seats/recommend_seats.
# - Only call get_theater_by_city if no theater_id/theater_name is present in the context or if the user asks to change the theater.
# - Only call get_movies_by_theaters if no movie_id/movie_title is present in the context or if the user asks to change the movie.
# - NEVER call book_tickets unless the user has explicitly said "yes", "confirm", "book them", or "book it".
# - If the user's city is not known (neither explicitly mentioned in the messages nor present in the "User's current city" system context), you MUST ask the user which city they are in. DO NOT guess the city, and DO NOT call get_theater_by_city without knowing the city.
# - If the user's city is known, use that city for all theater and movie searches.
# - ALWAYS use the selected booking date provided in the system messages when calling tools. DO NOT guess any date. If the user doesn't specify a date, it defaults to today.
# - if user says "rebook last time" — extract show details from conversation history.
# - NEVER book tickets or recommend seats without having a selected showtime first. If the user asks to book tickets (e.g., "book 2 tickets" or "book my tickets") but has NOT selected a theater, movie, or showtime yet, you MUST NOT proceed to seat selection or booking. Instead, list available movies/theaters, show the available showtimes, and ask them to choose a showtime first.
# - Even if the theater, movie, and showtime are present in the "Current booking context" or resolved implicitly, if the user directly asks to book tickets (e.g., "i wanna book 14 tickets for animal", "book 3 seats") and has not explicitly chosen or confirmed the showtime in the chat history, you MUST NOT call recommend_seats or book_tickets immediately. Instead, first present the showtime details (theater, movie, date, time) to the user and ask them to confirm if they want to select this showtime.
# - If you are required to ask the user to confirm or choose a showtime before calling recommend_seats or book_tickets, you MUST STOP executing tools immediately and reply to the user textually. Do NOT call get_showtimes, get_available_seats, or any search tools in a loop.
# - EXCEPTION: If the user has just completed and confirmed a booking for a specific movie, theater, and showtime in the immediate chat history (e.g., they just successfully booked 10 tickets out of a larger request), and is now booking the remaining tickets (e.g., saying "now for 2", "book the other 2"), the showtime is considered verified and selected. You do NOT need to ask them to confirm the showtime again. Proceed directly to recommend_seats for the remaining number of tickets.
# - Once the user explicitly selects/confirms the showtime (e.g. saying "yes", "proceed", "that works"), then use recommend_seats to find the best available seats and present them to the user for confirmation.
# - If the user requests to book more than 10 tickets (or asks for more than 10 seats):
#   1. Explain to the user that the system allows a maximum of 10 tickets per booking transaction.
#   2. Offer to book the first 10 tickets/seats first, and explain that they can book the remaining tickets in subsequent transactions.
#   3. Call recommend_seats or book_tickets with a maximum of 10 seats (e.g., the first 10 seats or a recommendation for 10 seats). NEVER pass more than 10 seats or a num_seats/num_tickets value greater than 10 to any tool.
#   4. Once those 10 are drafted, present the booking summary to the user for confirmation. Do NOT try to call booking tools again in a loop within the same turn.
# - After book_tickets returns a draft, tell user the booking summary and await confirmation.
# - Always show: movie title, theater name, screen, date, time, seats, total price.
# """

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



from langchain_core.runnables import RunnableConfig

def booking_node(state: BookingAgentState, config: RunnableConfig) -> BookingAgentState:
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

    # Build a single consolidated system message containing all active context
    context_lines = []
    
    city = state.get("city")
    if city:
        context_lines.append(f"User's current city: {city}")
        
    # Inject context (IDs and Names) so LLM knows selected theater/movie/show
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
        context_lines.append("Current booking context:\n" + "\n".join(context_parts))
        
    context_lines.append(f"Today's date: {today_str}\nSelected booking date: {date}")
    
    combined_context_msg = SystemMessage(content="\n\n".join(context_lines))

    # Keep conversation history (HumanMessage, AIMessage)
    input_messages = [
        m for m in state.get("messages", [])
        if getattr(m, "type", None) == "human" or (getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None))
    ]
    
    # Prepend the single, consolidated system context message
    input_messages = [combined_context_msg] + input_messages

    agent_state = {**state, "messages": input_messages}

    try:
        agent_config = {**config, "recursion_limit": 30}
        result = booking_react_agent.invoke(agent_state, config=agent_config)
    except Exception as e:
        if "recursion_limit" in str(e).lower() or "recursion" in str(e).lower():
            logger.error(f"Booking agent recursion limit reached: {e}")
            msg = AIMessage(content="I encountered a processing loop. Please try your request again with simpler terms or one step at a time.")
            return {
                **state,
                "messages": [msg]
            }
        raise e

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

    returned_messages = extract_new_messages(input_messages, result["messages"])
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