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


class theater_by_city(BaseModel):
    city : str


class movies_now_showing(BaseModel):
    theater_ids : list[str]
    date : str | None 

class showtimes_request(BaseModel):
    movie_id: str
    theater_id: str
    date: str


class seat_map_request(BaseModel):
    movie_id: str
    theater_id: str
    show_id: str

class seats_types_available(BaseModel):
    movie_id: str
    theater_id: str
    show_id: str
    seat_type: list[str]

class seats_available(BaseModel):
    movie_id:str
    theater_id:str
    show_id:str
    seats: list[str]

class current_movies(BaseModel):
    city: str
    date: str

class RecommendMoviesRequest(BaseModel):
    genres: list[str]
    city: str
    language: str | None = None
    limit: int = 5  # max recommendations to return

class RecommendTheatersRequest(BaseModel):
    movie_id: str
    city: str

