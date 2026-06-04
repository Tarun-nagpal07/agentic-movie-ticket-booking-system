from pydantic import BaseModel, field_validator, model_validator
from src.config.constants import BookingStatus, SeatType, Limits

class BookingRequest(BaseModel):
    show_id : str
    seats : list[str]
    num_tickets : int

    @field_validator('num_tickets')
    def validate_num_tickets(cls, v):
        if v < 1 or v > Limits.MAX_TICKETS_PER_BOOKING:
            raise ValueError(f'Number of tickets must be between 1 and {Limits.MAX_TICKETS_PER_BOOKING}')
        return v
    
    @model_validator(mode='after')
    def seats_match_tickets(self):
        if len(self.seats) != self.num_tickets:
            raise ValueError('Number of seats must match number of tickets')
        return self
    
class BookingResponse(BaseModel):
    booking_id : str
    # show_id :str
    # user_id : str
    status: BookingStatus
    total_price: int
    seats: list[str]
    booked_at: str

class CancelRequest(BaseModel):
    booking_id : str
    reason : str | None

class RefundResponse(BaseModel):
    refund_id: str
    amount: float

class GetBookingRequest(BaseModel):
    booking_id: str

class GetBookingsByStatusRequest(BaseModel):
    status : str