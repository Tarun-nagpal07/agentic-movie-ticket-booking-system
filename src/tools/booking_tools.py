from src.utils.logger import get_logger
from src.utils.errors import handle_errors, ToolError,BookingError
from src.db.json_store import load_db, save_db
from src.config.constants import DBFile,SeatStatus
from langchain_core.tools import tool
from src.utils.date_utils import get_today, get_now, is_show_in_future
from src.schemas.show import Theater, Movie, ShowTime


logger = get_logger(__name__)

@tool("get_theater_by_city")
@handle_errors(error_class=ToolError)
def get_theater_by_city(city: str) -> list[Theater]:
    """
    Get all theaters in a given city.
    Use when user asks about theaters or movies available in a city.

    Args:
        city: city name — ahmedabad, mumbai, delhi, bangalore
    """
    db = load_db(DBFile.THEATERS)

    theaters = db[DBFile.THEATERS].get(city.lower())

    if theaters is None:
        raise ToolError(
            message=f"No theaters found for city: {city}",
            code = "NO_THEATERS_FOUND",
            recoverable=True
        )
    logger.info(f"found {len(theaters)} theaters in {city}")
    return {"status":"success","theaters":theaters}


@tool("get_movies_now_showing",args_schema={"theater_ids": list[str], "date": str | None})
@handle_errors(error_class=ToolError)
def get_movies_now_showing(theater_ids: list[str], date: str = None) -> dict:
    """
    Get all movies currently showing across given theaters on a date.
    Use after get_theaters_by_city to find what movies are playing.

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
                movies_showing.append(movies_lookup[movie_id])

        result[tid] = movies_showing

    if not any(result.values()):
        raise ToolError(
            message=f"No movies showing on {date} in the given theaters.",
            code="NO_MOVIES_FOUND",
            recoverable=True
        )

    logger.info(f"found movies for {len(result)} theaters on {date}")
    return {"status": "success", "date": date, "movies_by_theater": result}


@tool("get_showtimes",args_schema={"movie_id": str, "theater_id": str, "date": str})
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

    theater_shows = db["showtimes"].get(theater_id)
    if not theater_shows:
        raise ToolError(
            message=f"No showtimes found for theater '{theater_id}'.",
            code="THEATER_NOT_FOUND",
            recoverable=True
        )

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

    # attach available seat count to each show
    for show in shows_on_date:
        show["seats_available"] = sum(
            1 for status in show["seats"].values()
            if status == SeatStatus.AVAILABLE
        )

    logger.info(f"found {len(shows_on_date)} shows for movie {movie_id} on {date}")
    return {"status": "success", "shows": shows_on_date}



@tool("book_tickets")
@handle_errors(error_class=BookingError)
def book_tickets(user_id: str, show_id: str, seats: list[str], num_tickets: int) -> dict:
    """
    Book tickets for a show. Confirms seat availability, creates booking record,
    and updates seat status to booked.
    Use only after user has confirmed the booking details.

    Args:
        user_id: user ID e.g. "u1"
        show_id: show ID e.g. "s101"
        seats: list of seat IDs to book e.g. ["E5", "E6"]
        num_tickets: number of tickets — must match length of seats
    """
    if len(seats) != num_tickets:
        raise BookingError(
            message="Number of seats must match num_tickets.",
            code="SEATS_MISMATCH",
            recoverable=True
        )

    showtimes_db = load_db(DBFile.SHOWTIMES)
    bookings_db  = load_db(DBFile.BOOKINGS)

    # find the show across all theaters and movies
    show = None
    theater_id = None
    movie_id = None

    for tid, movies in showtimes_db["showtimes"].items():
        for mid, shows in movies.items():
            for s in shows:
                if s["show_id"] == show_id:
                    show = s
                    theater_id = tid
                    movie_id = mid
                    break

    if not show:
        raise BookingError(
            message=f"Show '{show_id}' not found.",
            code="SHOW_NOT_FOUND",
            recoverable=True
        )

    # check show is in future
    if not is_show_in_future(show["date"], show["time"]):
        raise BookingError(
            message=f"Cannot book — show has already started or passed.",
            code="SHOW_ALREADY_STARTED",
            recoverable=False
        )

    # check all seats are available
    unavailable = [
        seat for seat in seats
        if show["seats"].get(seat) != SeatStatus.AVAILABLE
    ]
    if unavailable:
        raise BookingError(
            message=f"Seats {unavailable} are not available.",
            code="SEATS_NOT_AVAILABLE",
            recoverable=True
        )

    # calculate total price
    total_price = show["price"] * num_tickets

    # generate booking id
    booking_id = f"b_{len(bookings_db['bookings']) + 1:03d}"
    booked_at  = get_now()

    # build booking record
    new_booking = {
        "booking_id":   booking_id,
        "user_id":      user_id,
        "movie_id":     movie_id,
        "theater_id":   theater_id,
        "screen_no":    show["screen_no"],
        "screen_name":  show["screen_name"],
        "show_id":      show_id,
        "show_date":    show["date"],
        "show_time":    show["time"],
        "format":       show["format"],
        "seats":        seats,
        "num_tickets":  num_tickets,
        "price_per_ticket": show["price"],
        "total_price":  total_price,
        "status":       "confirmed",
        "booked_at":    booked_at,
        "refund_amount": None,
        "cancelled_at":  None
    }

    # write booking
    bookings_db["bookings"][booking_id] = new_booking
    save_db(DBFile.BOOKINGS, bookings_db)

    # flip seats to booked in showtimes
    for seat in seats:
        showtimes_db["showtimes"][theater_id][movie_id][
            next(i for i, s in enumerate(
                showtimes_db["showtimes"][theater_id][movie_id]
            ) if s["show_id"] == show_id)
        ]["seats"][seat] = SeatStatus.BOOKED

    save_db(DBFile.SHOWTIMES, showtimes_db)

    logger.info(f"booking {booking_id} confirmed for user {user_id}")
    return {
        "status":       "success",
        "booking_id":   booking_id,
        "total_price":  total_price,
        "seats":        seats,
        "show_date":    show["date"],
        "show_time":    show["time"],
        "screen_name":  show["screen_name"],
        "booked_at":    booked_at
    }