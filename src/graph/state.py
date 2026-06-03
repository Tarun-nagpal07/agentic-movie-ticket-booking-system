from typing import TypedDict
# from src.config.constants.intents import Intent

class BookingState(TypedDict):
    messages : list[str]
    user_id : str
    intent : str
    city : str | None
    search_results : list | None
    booking_draft : dict | None
    confirmed : bool | None
    error_message : str | None
    memory : dict 
