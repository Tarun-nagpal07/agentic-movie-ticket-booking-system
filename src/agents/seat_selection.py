from langchain.agents import create_agent
from src.agents.llm import get_llm
from src.graph.state import SeatAgentState
from src.tools.seat_tools import (
    get_seat_map,
    get_seats_types_available,
    get_seats_available
)

from src.utils.id_cleaner import remove_raw_ids
from langchain_core.messages import AIMessage
from src.utils.logger import get_logger
from src.agents.middleware import trim_messages
logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a seat selection assistant for movie ticket booking.
Your job is to show REAL seat availability from the theater system.

[CRITICAL RULE: CONCEAL ALL DATABASE IDS]
- NEVER display, print, or mention raw database IDs (such as theater_id, movie_id, show_id, e.g. 't1', 'm2', 's101') in your final text responses or listings shown to the user.
- If a tool returns IDs, keep them hidden in the background for tool calling purposes. ONLY present readable names.
- DO NOT print "(Theater ID: ...)" or "(Movie ID: ...)" or "(ID: ...)" or show IDs in your output.

Tools and when to use them:
- get_seat_map              : call first — gets the full real seat layout for the show
- get_seats_types_available : call to filter by row type using ROW LETTERS not type names
- get_seats_available       : call to check if specific seat IDs are available

CRITICAL rules — read carefully:
- NEVER guess any available seats, seat counts, seat types, rows, theater names, movie titles, show times, or dates. If any value is missing or unclear, ask the user to clarify instead of guessing.
- ALWAYS check the "Current booking context" system message first for `theater_id`, `movie_id`, and `show_id`. You MUST use these values directly as tool arguments for get_seat_map and get_seats_available instead of asking the user or searching for them.
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
1. call get_seat_map(theater_id, movie_id, show_id) using IDs from the "Current booking context" system message.
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
    from langchain_core.messages import SystemMessage

    # 1. Extract entities from the latest user message
    text_updates = {}
    latest_human_msg = next((m.content for m in reversed(state.get("messages", [])) if getattr(m, "type", None) == "human"), "")
    if latest_human_msg:
        text_updates = extract_entities_from_text(latest_human_msg)

    from src.utils.date_utils import get_today
    today_str = get_today()
    date = state.get("date") or today_str
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

    # Inject current date and selected date context
    from src.utils.date_utils import get_today
    today_str = get_today()
    date = state.get("date") or today_str
    input_messages = [SystemMessage(content=f"Today's date: {today_str}\nSelected booking date: {date}")] + input_messages

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
        "messages":       cleaned_messages,
        "seat_map":       seat_map,
        "available_seats": available_seats,
        "theater_id":   final_theater_id,
        "theater_name": final_theater_name,
        "movie_id":     final_movie_id,
        "movie_title":  final_movie_title,
        "show_id":      final_show_id,
    }