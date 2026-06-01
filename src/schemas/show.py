from pydantic import BaseModel
from src.config.constants import SeatType, ScreenFormat, SeatStatus


class Movie(BaseModel):
    movie_id : str
    title : str
    genre : list[str]
    language : str
    duration : int  # in minutes
    rating : float  # out of 10

class Screen(BaseModel):
    screen_no : int
    name : str
    format : ScreenFormat
    capacity : int

class Theater(BaseModel):
    theater_id : str
    name : str
    city : str
    screens : list[Screen]
    latitude : float
    longitude : float
    parking : bool
    amenities : list[str]

class ShowTime(BaseModel):
    show_id: str
    movie_id: str
    theater_id: str
    screen_no: int
    screen_name: str
    date: str
    time: str
    format: ScreenFormat
    price: int
    seats: dict[str, SeatStatus]
    seat_types: dict[str, SeatType]