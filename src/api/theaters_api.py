from fastapi import APIRouter, Depends, HTTPException, status
from src.api import services
from src.api.rate_limiter import RateLimiter

router = APIRouter()

rate_limit_dep = Depends(RateLimiter(limit=30, window=60, scope="theaters_api"))

@router.get("/", dependencies=[rate_limit_dep])
def list_theaters(city: str = None):
    if city:
        theaters = services.get_theaters_by_city(city)
    else:
        # default to all if no city is specified, or Ahmedabad
        theaters = services.get_theaters_by_city("ahmedabad")
    return {"status": "success", "theaters": theaters}

@router.get("/{theater_id}", dependencies=[rate_limit_dep])
def get_theater(theater_id: str):
    theater = services.get_theater_by_id(theater_id)
    if not theater:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Theater with ID '{theater_id}' not found"
        )
    return {"status": "success", "theater": theater}
