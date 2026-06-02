from src.utils.logger import get_logger
from src.db.json_store import load_db, DBFile
from src.schemas.show import seat_map_request,seats_types_available,seats_available
from langchain.tools import tool
from src.utils.errors import handle_errors, ToolError


logger = get_logger(__name__)


@tool("get_seat_map",args_schema=seat_map_request)
@handle_errors(error_class=ToolError)
def get_seat_map(theater_id: str, movie_id: str,show_id: str) -> dict:
    """
    Get seat map for a given showtime.
    theater_id and movie_id are required you can call other agent to get details.
    this tools list all seats with their status (available/booked) for a given showtime.
    Args:
        theater_id: ID of the theater
        movie_id: ID of the movie
        date: date in YYYY-MM-DD format
    """
    
    showtimes_db = load_db(DBFile.SHOWTIMES)
    theater_shows = showtimes_db["showtimes"].get(theater_id,{})
    movie_shows = theater_shows.get(movie_id,[])
    show = next(
    (s for s in movie_shows if s["show_id"] == show_id),
    None
    )

    if not show:
        raise ToolError(
            message=f"No show found for show_id: {show_id}, theater_id: {theater_id}, movie_id: {movie_id}",
            code = "NO_SHOWTIMES_FOUND",
            recoverable=True
        )

    logger.info(f"Seats found for show_id: {show_id}, theater_id: {theater_id}, movie_id: {movie_id} ")
    return {"status":"success","seats" : show["seats"], "seat_types": show["seat_types"]}

@tool("get_seats_types_available",args_schema=seats_types_available)
@handle_errors(error_class=ToolError)
def get_seats_types_available(theater_id:str,movie_id:str,show_id:str,seat_type:list[str])->dict:
    """
    Get available seats for a given showtime and seat type.
    Use after get_movies_now_showing to find showtimes for a movie.
    Args:
        theater_id: ID of the theater
        movie_id: ID of the movie
        show_id: ID of the show
        seat_type: List of seat_types ["A","B","C","D","E"]
    """

    showtimes_db = load_db(DBFile.SHOWTIMES)
    theater_shows = showtimes_db["showtimes"].get(theater_id,{})
    movie_shows = theater_shows.get(movie_id,[])
    show = next(
    (s for s in movie_shows if s["show_id"] == show_id),
    None
    )

    if not show:
        raise ToolError(
            message=f"No show found for show_id: {show_id}, theater_id: {theater_id}, movie_id: {movie_id}",
            code = "NO_SHOWTIMES_FOUND",
            recoverable=True
        )


    seats_available = [s for s, t in show["seat_types"].items() if t in seat_type and show["seats"].get(s) == "available"]

    logger.info(f"{len(seats_available)} seats available for show_id: {show_id}, theater_id: {theater_id}, movie_id: {movie_id} for seat types: {seat_type}")
    return {"status":"success","available_seats": seats_available}

@tool("get_seats_available",args_schema=seats_available)
@handle_errors(error_class=ToolError)
def get_seats_available(theater_id:str,movie_id:str,show_id:str,seats:list[str])->dict:
    """
    Get available seats for a given showtime and seat type.
    Use after get_movies_now_showing to find showtimes for a movie.
    Args:
        theater_id: ID of the theater
        movie_id: ID of the movie
        show_id: ID of the show
        seats: List of seats example: ["A1","B1","A2","D4","E7"]
    """

    showtimes_db = load_db(DBFile.SHOWTIMES)
    theater_shows = showtimes_db["showtimes"].get(theater_id,{})
    movie_shows = theater_shows.get(movie_id,[])
    show = next(
    (s for s in movie_shows if s["show_id"] == show_id),
    None
    )

    if not show:
        raise ToolError(
            message=f"No show found for show_id: {show_id}, theater_id: {theater_id}, movie_id: {movie_id}",
            code = "NO_SHOWTIMES_FOUND",
            recoverable=True
        )


    seats_available = [s for s, t in show["seats"].items() if t in seats and show["seats"].get(s) == "available"]

    logger.info(f"{len(seats_available)} seats available for show_id: {show_id}, theater_id: {theater_id}, movie_id: {movie_id} for seats: {seats}")
    return {"status":"success","available_seats": seats_available}