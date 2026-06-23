from fastapi import APIRouter, Depends, HTTPException, status
from src.api import services
from src.api.rate_limiter import RateLimiter

router = APIRouter()

# Rate limiting dependency: 30 requests per 60 seconds
rate_limit_dep = Depends(RateLimiter(limit=30, window=60, scope="movies_api"))

@router.get("/", dependencies=[rate_limit_dep])
def list_movies(query: str = None):
    if query:
        movies = services.search_movies(query)
    else:
        movies = services.get_movies()
    return {"status": "success", "movies": movies}

@router.get("/{movie_id}", dependencies=[rate_limit_dep])
def get_movie(movie_id: str):
    movie = services.get_movie_by_id(movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with ID '{movie_id}' not found"
        )
    return {"status": "success", "movie": movie}
