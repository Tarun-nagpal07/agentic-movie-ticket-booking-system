from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List

from src.api import services
from src.api.auth import get_current_user
from src.api.rate_limiter import RateLimiter
from src.utils.date_utils import hours_until_show
from src.config.constants import BookingStatus, RefundPolicy

router = APIRouter()

# Rate limiting dependencies
rate_limit_list = Depends(RateLimiter(limit=20, window=60, scope="bookings_list"))
rate_limit_write = Depends(RateLimiter(limit=10, window=60, scope="bookings_write"))

class BookingCreateRequest(BaseModel):
    show_id: str
    seats: List[str]

class CancelRequest(BaseModel):
    reason: str = "User requested cancellation"

@router.get("/", dependencies=[rate_limit_list])
def list_bookings(current_user: dict = Depends(get_current_user)):
    bookings = services.get_user_bookings(current_user["user_id"])
    return {"status": "success", "bookings": bookings}

@router.get("/{booking_id}", dependencies=[rate_limit_list])
def get_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    booking = services.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking '{booking_id}' not found."
        )
    # Authorization check
    if booking["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this booking."
        )
    return {"status": "success", "booking": booking}

@router.post("/", dependencies=[rate_limit_write])
def create_booking(request: BookingCreateRequest, current_user: dict = Depends(get_current_user)):
    try:
        booking = services.create_booking(
            user_id=current_user["user_id"],
            show_id=request.show_id,
            seats=request.seats
        )
        return {"status": "success", "booking": booking}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create booking: {e}"
        )

@router.post("/{booking_id}/cancel", dependencies=[rate_limit_write])
def cancel_booking(booking_id: str, request: CancelRequest, current_user: dict = Depends(get_current_user)):
    booking = services.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking '{booking_id}' not found."
        )
    # Authorization check
    if booking["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to cancel this booking."
        )
        
    if booking["status"] == BookingStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is already cancelled."
        )

    # Calculate refund
    hours_left = hours_until_show(booking["show_date"], booking["show_time"])
    if hours_left <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel — show has already started or passed."
        )
    elif hours_left > RefundPolicy.FULL_REFUND_HOURS:
        refund_percent = RefundPolicy.FULL_REFUND_PERCENT
    elif hours_left > RefundPolicy.PARTIAL_REFUND_HOURS:
        refund_percent = RefundPolicy.PARTIAL_REFUND_PERCENT
    else:
        refund_percent = RefundPolicy.NO_REFUND_PERCENT

    refund_amount = round(booking["total_price"] * refund_percent, 2)
    
    cancelled_booking = services.cancel_booking(
        booking_id=booking_id,
        refund_amount=refund_amount,
        reason=request.reason
    )
    
    if not cancelled_booking:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process cancellation."
        )
        
    return {"status": "success", "booking": cancelled_booking}
