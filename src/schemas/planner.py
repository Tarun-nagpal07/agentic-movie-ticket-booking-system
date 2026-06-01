from pydantic import BaseModel
from src.config.constants import Intent


class PlannerResponse(BaseModel):
    intent: Intent
    city: str | None = None
    movie_title: str | None = None
    date: str | None = None