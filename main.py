from fastapi import FastAPI, status, Request
from fastapi.responses import JSONResponse

from src.utils.logger import get_logger
from src.db.postgres import init_db
from src.api.auth import router as auth_router
from src.api.movies_api import router as movies_router
from src.api.theaters_api import router as theaters_router
from src.api.showtimes_api import router as showtimes_router
from src.api.bookings_api import router as bookings_router
from src.api.users_api import router as users_router
from src.api.chat_api import router as chat_router

# Backward compatibility exports for scratch / test scripts
from src.utils.chat_utils import load_messages_from_postgress, get_active_interrupt

# Initialize logger
logger = get_logger("fastapi_app")

app = FastAPI(title="Movie Ticket Booking Chat API")

# Mount API routers
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(movies_router, prefix="/api/movies", tags=["movies"])
app.include_router(theaters_router, prefix="/api/theaters", tags=["theaters"])
app.include_router(showtimes_router, prefix="/api/showtimes", tags=["showtimes"])
app.include_router(bookings_router, prefix="/api/bookings", tags=["bookings"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])

# Initialize Database Schema & Auto-seed preferences if empty
init_db()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception in {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "error": str(exc)},
    )


@app.get("/")
def home():
    return {"message": "Movie Booking Assistant Chat API is running."}
