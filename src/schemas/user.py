from pydantic import BaseModel
from src.config.constants import SeatType , ScreenFormat

class UserPrefs(BaseModel):
    city : str
    favorite_genres : list[str]
    preferred_seat_type : SeatType
    preferred_screen_format : ScreenFormat
    prefered_theaters : list[str]
    language : str

class UserProfile(BaseModel):
    user_id: str
    name: str
    email: str
    latitude: float
    longitude: float
    city: str
    favorite_genres: list[str]
    preferred_theaters: list[str]
    preferred_seat_type: SeatType
    preferred_format: ScreenFormat
    language_pref: str
    booking_history: list[dict]