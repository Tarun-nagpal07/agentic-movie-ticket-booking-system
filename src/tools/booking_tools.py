from src.utils.logger import get_logger
from src.utils.errors import handle_errors, ToolError,BookingError
from src.db.json_store import load_db, save_db
from src.config.constants import DBFile,SeatStatus
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from src.utils.date_utils import get_today, get_now, is_show_in_future
from src.schemas.show import theater_by_city, movies_now_showing, showtimes_request, current_movies
from src.schemas.booking import BookingRequest

logger = get_logger(__name__)

@tool("get_theater_by_city",args_schema=theater_by_city)
@handle_errors(error_class=ToolError)
def get_theater_by_city(city: str) -> dict:
    """
    Get all theaters in a given city.
    Use when user asks about theaters or movies available in a city.

    Args:
        city: city name — ahmedabad, mumbai, delhi, bangalore
    """
    db = load_db(DBFile.THEATERS)

    theaters = db["theaters"].get(city.lower())

    if theaters is None:
        raise ToolError(
            message=f"No theaters found for city: {city}",
            code = "NO_THEATERS_FOUND",
            recoverable=True
        )
    
    cleaned = []
    for t in theaters:
        cleaned.append({
            "theater_id": t["theater_id"],
            "name": t["name"],
            "city": t["city"],
            "address": t["address"]
        })

    logger.info(f"found {len(cleaned)} theaters in {city}")
    return {"status":"success","theaters":cleaned}


@tool("get_movies", args_schema=current_movies)
@handle_errors(error_class=ToolError)
def get_movies_by_city(city: str, date: str | None = None) -> dict:
    """
    Get all movies currently showing in a city on a given date.

    Args:
        city: city name — ahmedabad, mumbai, delhi, bangalore
        date: date in YYYY-MM-DD format. Defaults to today if not provided.
    """
    date = date or get_today()

    theaters_db = load_db(DBFile.THEATERS)
    showtimes_db = load_db(DBFile.SHOWTIMES)
    movies_db = load_db(DBFile.MOVIES)

    theaters = theaters_db["theaters"].get(city.lower())

    if not theaters:
        raise ToolError(
            message=f"No theaters found in '{city}'.",
            code="CITY_NOT_FOUND",
            recoverable=True
        )

    movies_lookup = {
        movie["movie_id"]: movie
        for movie in movies_db["movies"]
    }

    movies_found = {}

    for theater in theaters:
        theater_id = theater["theater_id"]

        theater_shows = showtimes_db["showtimes"].get(theater_id, {})

        for movie_id, shows in theater_shows.items():

            has_show_on_date = any(
                show["date"] == date
                for show in shows
            )

            if has_show_on_date and movie_id in movies_lookup:
                m_info = movies_lookup[movie_id]
                movies_found[movie_id] = {
                    "movie_id": m_info["movie_id"],
                    "title": m_info["title"],
                    "genre": m_info.get("genre", []),
                    "language": m_info.get("language", ""),
                    "duration_min": m_info.get("duration_min"),
                    "rating": m_info.get("rating")
                }

    if not movies_found:
        raise ToolError(
            message=f"No movies showing in {city} on {date}.",
            code="NO_MOVIES_FOUND",
            recoverable=True
        )

    logger.info(
        f"found {len(movies_found)} movies in {city} on {date}"
    )

    return {
        "status": "success",
        "city": city,
        "date": date,
        "movies": list(movies_found.values())
    }


@tool("get_movies_now_showing",args_schema=movies_now_showing)
@handle_errors(error_class=ToolError)
def get_movies_by_theaters(theater_ids: list[str], date: str = None) -> dict:
    """
    Get all movies currently showing across given theaters on a date.
    Use after get_theaters_by_city to find what movies are playing on particular theaters.

    Args:
        theater_ids: list of theater IDs e.g. ["t1", "t2"]
        date: date in YYYY-MM-DD format. Defaults to today if not provided.
    """
    date = date or get_today()
    showtimes_db = load_db(DBFile.SHOWTIMES)
    movies_db = load_db(DBFile.MOVIES)

    movies_lookup = {m["movie_id"]: m for m in movies_db["movies"]}

    result = {}
    for tid in theater_ids:
        theater_shows = showtimes_db["showtimes"].get(tid, {})
        movies_showing = []

        for movie_id, shows in theater_shows.items():
            shows_on_date = [s for s in shows if s["date"] == date]
            if shows_on_date and movie_id in movies_lookup:
                m_info = movies_lookup[movie_id]
                movies_showing.append({
                    "movie_id": m_info["movie_id"],
                    "title": m_info["title"],
                    "genre": m_info.get("genre", []),
                    "language": m_info.get("language", ""),
                    "duration_min": m_info.get("duration_min"),
                    "rating": m_info.get("rating")
                })

        result[tid] = movies_showing

    if not any(result.values()):
        raise ToolError(
            message=f"No movies showing on {date} in the given theaters.",
            code="NO_MOVIES_FOUND",
            recoverable=True
        )

    logger.info(f"found movies for {len(result)} theaters on {date}")
    return {"status": "success", "date": date, "movies_by_theater": result}

@tool("get_showtimes",args_schema=showtimes_request)
@handle_errors(error_class=ToolError)
def get_showtimes(movie_id: str, theater_id: str, date: str = None) -> dict:
    """
    Get showtimes for a movie at a theater.
    Use movie_id and theater_id from get_movies_now_showing results.

    Args:
        movie_id: from get_movies_now_showing result e.g. "m1"
        theater_id: from get_theater_by_city result e.g. "t1"
        date: YYYY-MM-DD, defaults to today
    """
    date = date or get_today()
    db = load_db(DBFile.SHOWTIMES)

    # 0. If movie_id is actually a show_id (e.g. starting with "s")
    if movie_id and movie_id.startswith("s"):
        resolved_mid = None
        resolved_tid = None
        for tid, movie_shows in db["showtimes"].items():
            for mid, shows in movie_shows.items():
                for s in shows:
                    if s["show_id"] == movie_id:
                        resolved_mid = mid
                        resolved_tid = tid
                        break
                if resolved_mid:
                    break
            if resolved_mid:
                break
        if resolved_mid:
            logger.info(f"Resolved show_id '{movie_id}' as movie_id '{resolved_mid}' at theater '{resolved_tid}'")
            movie_id = resolved_mid
            theater_id = resolved_tid

    # 1. Resolve theater_id if passed as name
    if theater_id not in db["showtimes"]:
        theaters_db = load_db(DBFile.THEATERS)
        resolved_tid = None
        for city, theaters_list in theaters_db["theaters"].items():
            for t in theaters_list:
                if t["name"].lower() == theater_id.lower() or theater_id.lower() in t["name"].lower():
                    resolved_tid = t["theater_id"]
                    break
            if resolved_tid:
                break
        if resolved_tid:
            theater_id = resolved_tid

    theater_shows = db["showtimes"].get(theater_id)
    if not theater_shows:
        raise ToolError(
            message=f"No showtimes found for theater '{theater_id}'.",
            code="THEATER_NOT_FOUND",
            recoverable=True
        )

    # 2. Resolve movie_id if passed as title
    if movie_id not in theater_shows:
        movies_db = load_db(DBFile.MOVIES)
        resolved_mid = None
        for m in movies_db["movies"]:
            if m["title"].lower() == movie_id.lower() or movie_id.lower() in m["title"].lower():
                resolved_mid = m["movie_id"]
                break
        if resolved_mid:
            movie_id = resolved_mid

    movie_shows = theater_shows.get(movie_id)
    if not movie_shows:
        raise ToolError(
            message=f"Movie '{movie_id}' is not showing at theater '{theater_id}'.",
            code="MOVIE_NOT_AT_THEATER",
            recoverable=True
        )

    shows_on_date = [s for s in movie_shows if s["date"] == date]
    if not shows_on_date:
        raise ToolError(
            message=f"No shows for movie '{movie_id}' on {date} at theater '{theater_id}'.",
            code="NO_SHOWS_ON_DATE",
            recoverable=True
        )

    cleaned_shows = []
    for show in shows_on_date:
        seats_available = sum(
            1 for status in show["seats"].values()
            if status == SeatStatus.AVAILABLE
        )
        cleaned_shows.append({
            "show_id": show["show_id"],
            "movie_id": show["movie_id"],
            "theater_id": show["theater_id"],
            "screen_no": show["screen_no"],
            "screen_name": show["screen_name"],
            "date": show["date"],
            "time": show["time"],
            "format": show["format"],
            "price": show["price"],
            "seats_available": seats_available
        })

    logger.info(f"found {len(cleaned_shows)} shows for movie {movie_id} on {date}")
    return {"status": "success", "shows": cleaned_shows}


@tool("book_tickets",args_schema=BookingRequest)
@handle_errors(error_class=BookingError)
def book_tickets(show_id: str, seats: list[str], num_tickets: int, config: RunnableConfig) -> dict:
    """
    Validates and prepares a booking draft.
    Does NOT confirm the booking — confirmation happens separately.

    Args:
        show_id: from get_showtimes result
        seats: from recommend_seats result
        num_tickets: must match len(seats)
    """
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        raise BookingError(
            message="User ID not found in context.",
            code="USER_ID_NOT_FOUND",
            recoverable=False
        )

    if len(seats) != num_tickets:
        raise BookingError(
            message="Number of seats must match num_tickets.",
            code="SEATS_MISMATCH",
            recoverable=True
        )

    showtimes_db = load_db(DBFile.SHOWTIMES)
    bookings_db  = load_db(DBFile.BOOKINGS)

    # find show
    show = theater_id = movie_id = None
    for tid, movies in showtimes_db["showtimes"].items():
        for mid, shows in movies.items():
            for s in shows:
                if s["show_id"] == show_id:
                    show, theater_id, movie_id = s, tid, mid
                    break

    if not show:
        raise BookingError(message=f"Show '{show_id}' not found.", code="SHOW_NOT_FOUND", recoverable=True)

    if not is_show_in_future(show["date"], show["time"]):
        raise BookingError(message="Show has already started or passed.", code="SHOW_ALREADY_STARTED", recoverable=False)

    unavailable = [s for s in seats if show["seats"].get(s) != SeatStatus.AVAILABLE]
    if unavailable:
        raise BookingError(message=f"Seats {unavailable} are not available.", code="SEATS_NOT_AVAILABLE", recoverable=True)

    # build draft — do NOT write to JSON yet
    booking_id  = f"b_{len(bookings_db['bookings']) + 1:03d}"
    total_price = show["price"] * num_tickets

    draft = {
        "booking_id":       booking_id,
        "user_id":          user_id,
        "movie_id":         movie_id,
        "theater_id":       theater_id,
        "screen_no":        show["screen_no"],
        "screen_name":      show["screen_name"],
        "show_id":          show_id,
        "show_date":        show["date"],
        "show_time":        show["time"],
        "format":           show["format"],
        "seats":            seats,
        "seat_types":       show.get("seat_types", {}),  # for memory agent seat pref inference
        "num_tickets":      num_tickets,
        "price_per_ticket": show["price"],
        "total_price":      total_price,
        "status":           "pending",
        "booked_at":        get_now(),
        "refund_amount":    None,
        "cancelled_at":     None
    }

    logger.info(f"booking draft prepared for show {show_id} user {user_id}")

    # return draft into state — graph confirm node handles the rest
    return {"status": "draft", "booking_draft": draft}