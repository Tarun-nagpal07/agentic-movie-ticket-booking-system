import re
from src.utils.logger import get_logger
from src.schemas.show import get_available_seats_request, recommend_seats_request
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from src.utils.errors import handle_errors, ToolError
from src.tools.booking_tools import _resolve_movie_name_to_id
from src.api import services

logger = get_logger(__name__)


from src.utils.seat_map import generate_seat_grid_html


@tool("get_available_seats", args_schema=get_available_seats_request)
@handle_errors(error_class=ToolError)
def get_available_seats(
    theater_id: str,
    movie_id: str | None = None,
    show_id: str = None,
    seat_type: str | None = None,
    movie_name: str | None = None
) -> dict:
    """
    Get all AVAILABLE seats for a showtime. Optionally filter by seat type.
    Always call this before booking to get real available seat IDs.

    Args:
        theater_id: ID of the theater e.g. "t1"
        movie_id: ID of the movie e.g. "m1" (optional if movie_name provided)
        show_id: ID of the show e.g. "s101"
        seat_type: optional filter — "standard", "premium", or "recliner"
        movie_name: optional fuzzy movie name to resolve movie_id
    
    Returns grouped available seats with row labels, types, and seat IDs.
    ONLY these seat IDs can be used in book_tickets.
    """
    if movie_name:
        resolved = _resolve_movie_name_to_id(movie_name)
        if resolved:
            movie_id = resolved
    elif movie_id and not re.match(r"^m\d+$", movie_id.strip()):
        resolved = _resolve_movie_name_to_id(movie_id)
        if resolved:
            movie_id = resolved

    show = services.get_show_details(show_id)
    if not show:
        raise ToolError(
            message=f"No show found for show_id: {show_id}, theater_id: {theater_id}, movie_id: {movie_id}",
            code="NO_SHOWTIMES_FOUND",
            recoverable=True
        )

    seats_dict = services.get_show_seats(show_id)

    # Filter seats to only available ones and group by row
    available_seats = []
    seats_by_row = {}
    
    # Sort seats properly using natural/numerical sorting
    def seat_sort_key(seat_id):
        match = re.match(r"^([A-Z]+)(\d+)$", seat_id)
        if match:
            row, num = match.groups()
            return (row, int(num))
        return (seat_id, 0)

    sorted_seat_ids = sorted(seats_dict.keys(), key=seat_sort_key)

    for seat_id in sorted_seat_ids:
        status = seats_dict[seat_id]
        if status == "available":
            row_letter = seat_id[0]
            stype = show["seat_types"].get(row_letter)
            
            if seat_type and stype != seat_type.lower():
                continue
                
            seats_by_row.setdefault(row_letter, []).append(seat_id)

    rows_list = []
    total_available = 0
    for r in sorted(seats_by_row.keys()):
        row_seats = seats_by_row[r]
        stype = show["seat_types"].get(r)
        rows_list.append({
            "row": r,
            "type": stype,
            "seats": row_seats
        })
        total_available += len(row_seats)

    logger.info(f"Seats found for show_id: {show_id}, theater_id: {theater_id}, movie_id: {movie_id}")
    seat_map_tag = f"[SEAT_MAP:{show_id}]"
    return {
        "status": "success",
        "total_available": total_available,
        "rows": rows_list,
        "seat_map_tag": seat_map_tag
    }


@tool("recommend_seats", args_schema=recommend_seats_request)
@handle_errors(error_class=ToolError)
def recommend_seats(
    theater_id: str,
    movie_id: str | None = None,
    show_id: str = None,
    num_seats: int = 1,
    user_id: str | None = None,
    seat_type: str | None = None,
    movie_name: str | None = None,
    config: RunnableConfig = None
) -> dict:
    """
    Recommend the best available consecutive seats using user history + real availability.
    Use when user says "pick best seats", "recommend seats", "book X tickets".
    Returns seat IDs guaranteed available — pass directly to book_tickets.

    Args:
        theater_id: ID of the theater e.g. "t1"
        movie_id: ID of the movie e.g. "m1" (optional if movie_name provided)
        show_id: ID of the show e.g. "s101"
        num_seats: how many seats to find
        user_id: (optional) pass from context — enables history-driven preference
        seat_type: (optional) explicit override — "standard", "premium", "recliner"
        movie_name: (optional) fuzzy movie name to resolve movie_id
    """
    if movie_name:
        resolved = _resolve_movie_name_to_id(movie_name)
        if resolved:
            movie_id = resolved
    elif movie_id and not re.match(r"^m\d+$", movie_id.strip()):
        resolved = _resolve_movie_name_to_id(movie_id)
        if resolved:
            movie_id = resolved

    # Get user_id from config if not passed explicitly
    if not user_id and config:
        user_id = config.get("configurable", {}).get("user_id")

    # Resolve preferred seat type from user booking history
    preferred_type = seat_type
    based_on = "explicit request" if seat_type else "best available"
    
    if not preferred_type and user_id:
        try:
            user_bookings = services.get_user_bookings(user_id)
            confirmed = [b for b in user_bookings if b["status"] == "confirmed"]
            if confirmed:
                from collections import Counter
                type_counts = Counter()
                for b in confirmed:
                    st = b.get("seat_type")
                    if st:
                        type_counts[st] += 1
                if type_counts:
                    preferred_type = type_counts.most_common(1)[0][0]
                    based_on = "user history"
        except Exception as e:
            logger.error(f"Error loading user booking history: {e}")

    show = services.get_show_details(show_id)
    if not show:
        raise ToolError(
            message=f"No show found for show_id: {show_id}, theater_id: {theater_id}, movie_id: {movie_id}",
            code="NO_SHOWTIMES_FOUND",
            recoverable=True
        )

    seats_dict = services.get_show_seats(show_id)

    # Get all available seats
    available_seats = {s for s, status in seats_dict.items() if status == "available"}

    if len(available_seats) < num_seats:
        raise ToolError(
            message=f"Not enough seats available. Requested: {num_seats}, Available: {len(available_seats)}",
            code="NOT_ENOUGH_SEATS",
            recoverable=True
        )

    # Group all seats in showtimes by row letter
    seats_by_row = {}
    for s in seats_dict.keys():
        match = re.match(r"^([A-Z]+)(\d+)$", s)
        if match:
            r, num = match.groups()
            seats_by_row.setdefault(r, []).append(int(num))

    # Sort seat numbers in each row
    for r in seats_by_row:
        seats_by_row[r].sort()

    # Prioritize row selection: preferred type -> proximity to middle row
    sorted_rows = sorted(seats_by_row.keys())
    mid_idx = len(sorted_rows) // 2

    # Sorting rows prioritizing preferred seat_type, then proximity to middle row
    sorted_rows_by_pref = sorted(
        sorted_rows,
        key=lambda r: (
            0 if show["seat_types"].get(r) == preferred_type else 1,
            abs(sorted_rows.index(r) - mid_idx)
        )
    )

    # Algorithm to find consecutive seats closest to the middle of the row
    recommended = None
    for r in sorted_rows_by_pref:
        row_seats = seats_by_row[r]
        possible_blocks = []
        
        for i in range(len(row_seats) - num_seats + 1):
            window = row_seats[i : i + num_seats]
            
            # Check if seat numbers are consecutive
            is_consecutive = all(window[j] == window[0] + j for j in range(num_seats))
            seat_ids = [f"{r}{num}" for num in window]
            is_avail = all(sid in available_seats for sid in seat_ids)
            
            if is_consecutive and is_avail:
                # Calculate distance to middle of the row to get centered seats
                row_mid = (row_seats[0] + row_seats[-1]) / 2.0
                window_mid = (window[0] + window[-1]) / 2.0
                dist = abs(window_mid - row_mid)
                possible_blocks.append((dist, seat_ids))
                
        if possible_blocks:
            possible_blocks.sort(key=lambda x: x[0])
            recommended = possible_blocks[0][1]
            break

    # Fallback: pick N available seats even if not consecutive
    if not recommended:
        fallback_seats = []
        for r in sorted_rows_by_pref:
            for num in seats_by_row[r]:
                sid = f"{r}{num}"
                if sid in available_seats:
                    fallback_seats.append(sid)
                    if len(fallback_seats) == num_seats:
                        recommended = fallback_seats
                        based_on = f"{based_on} (non-consecutive)"
                        break
            if recommended:
                break

    # Determine recommended seat type
    rec_seat_type = None
    if recommended:
        rec_seat_type = show["seat_types"].get(recommended[0][0])

    logger.info(f"Recommended {recommended} seats for show_id: {show_id}")
    selected_seats_str = ",".join(recommended) if recommended else ""
    seat_map_tag = f"[SEAT_MAP:{show_id}:{selected_seats_str}]" if selected_seats_str else f"[SEAT_MAP:{show_id}]"
    return {
        "status": "success",
        "recommended_seats": recommended,
        "seat_type": rec_seat_type,
        "based_on": based_on,
        "seat_map_tag": seat_map_tag
    }


get_available_seats.handle_tool_error = True
recommend_seats.handle_tool_error = True