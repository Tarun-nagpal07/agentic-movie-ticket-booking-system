from fastapi import APIRouter, Depends, HTTPException, status
from src.api import services
from src.api.rate_limiter import RateLimiter

router = APIRouter()

rate_limit_dep = Depends(RateLimiter(limit=30, window=60, scope="showtimes_api"))

@router.get("/", dependencies=[rate_limit_dep])
def get_showtimes(theater_id: str, movie_id: str, date: str):
    """
    Get showtimes for a theater, movie, and date (YYYY-MM-DD).
    """
    shows = services.get_showtimes(theater_id, movie_id, date)
    return {"status": "success", "shows": shows}

@router.get("/{show_id}/seats", dependencies=[rate_limit_dep])
def get_show_seats(show_id: str):
    """
    Get seat status for a showtime.
    """
    show = services.get_show_details(show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Showtime '{show_id}' not found."
        )
    seats = services.get_show_seats(show_id)
    return {
        "status": "success",
        "show_id": show_id,
        "price": show["price"],
        "seat_types": show["seat_types"],
        "seats": seats
    }
