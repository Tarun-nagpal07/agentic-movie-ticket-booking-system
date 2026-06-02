from langchain.tools import tool
from src.db.json_store import load_db, save_db
from src.config.constants import DBFile, BookingStatus, RefundPolicy
from src.utils.errors import handle_errors, ToolError, BookingError
from src.utils.date_utils import get_now, hours_until_show
from src.utils.logger import get_logger
from src.schemas.booking import (
    CancelRequest,
    RefundResponse,
    GetBookingRequest
)

logger = get_logger(__name__)


@tool("get_booking_by_id",args_schema=GetBookingRequest)
@handle_errors(error_class=ToolError)
def get_booking_by_id(booking_id:str) -> dict:
    """
    Get booking details by booking ID.
    Use when user asks to cancel a booking or check booking status.

    Args:
        booking_id: booking ID e.g. "b_001"
    """
    db = load_db(DBFile.BOOKINGS)
    booking = db['bookings'].get(booking_id)

    if not booking:
        raise ToolError(
            message=f"No booking found for booking_id: {booking_id}",
            code ="BOOKING_NOT_FOUND",
            recoverable=True
        )
    
    if booking["status"] == BookingStatus.CANCELLED:
       raise ToolError(
            message=f"Booking '{booking_id}' is already cancelled.",
            code="BOOKING_ALREADY_CANCELLED",
            recoverable=False
        )

    logger.info(f"booking {booking_id} fetched")
    return {"status": "success", "booking": booking}



@tool("prepare_cancellation", args_schema=CancelRequest)
@handle_errors(error_class=BookingError)
def prepare_cancellation(booking_id: str, reason: str = None) -> dict:
    """
    Validates cancellation eligibility and calculates refund amount.
    Does NOT cancel the booking — cancellation happens after user approval.
    Always call get_booking_by_id first to confirm booking exists.

    Args:
        booking_id: booking ID to cancel e.g. "b_001"
        reason: optional reason for cancellation
    """
    db = load_db(DBFile.BOOKINGS)
    booking = db["bookings"].get(booking_id)

    if not booking:
        raise BookingError(
            message=f"Booking '{booking_id}' not found.",
            code="BOOKING_NOT_FOUND",
            recoverable=True
        )

    if booking["status"] == BookingStatus.CANCELLED:
        raise BookingError(
            message=f"Booking '{booking_id}' is already cancelled.",
            code="BOOKING_ALREADY_CANCELLED",
            recoverable=False
        )

    # calculate refund based on hours until show
    hours_left = hours_until_show(booking["show_date"], booking["show_time"])

    if hours_left <= 0:
        raise BookingError(
            message="Cannot cancel — show has already started or passed.",
            code="SHOW_ALREADY_STARTED",
            recoverable=False
        )
    elif hours_left > RefundPolicy.FULL_REFUND_HOURS:
        refund_percent = RefundPolicy.FULL_REFUND_PERCENT
        refund_message = "Full refund (90%) — cancelled more than 24 hours before show."
    elif hours_left > RefundPolicy.PARTIAL_REFUND_HOURS:
        refund_percent = RefundPolicy.PARTIAL_REFUND_PERCENT
        refund_message = "Partial refund (50%) — cancelled between 2 and 24 hours before show."
    else:
        refund_percent = RefundPolicy.NO_REFUND_PERCENT
        refund_message = "No refund — cancelled less than 2 hours before show."

    refund_amount = round(booking["total_price"] * refund_percent, 2)

    # build cancellation draft — do NOT write yet
    cancel_draft = {
        "booking_id":    booking_id,
        "user_id":       booking["user_id"],
        "movie_id":      booking["movie_id"],
        "theater_id":    booking["theater_id"],
        "show_id":       booking["show_id"],
        "show_date":     booking["show_date"],
        "show_time":     booking["show_time"],
        "seats":         booking["seats"],
        "total_price":   booking["total_price"],
        "refund_amount": refund_amount,
        "refund_message": refund_message,
        "reason":        reason,
        "hours_until_show": round(hours_left, 1)
    }

    logger.info(f"cancellation draft prepared for booking {booking_id} — refund: {refund_amount}")
    return {"status": "draft", "cancel_draft": cancel_draft}


@tool("process_refund", args_schema=RefundResponse)
@handle_errors(error_class=BookingError)
def process_refund(booking_id: str, refund_amount: float) -> dict:
    """
    Processes refund for a cancelled booking.
    Only call after cancellation has been confirmed and booking status updated.

    Args:
        booking_id: booking ID e.g. "b_001"
        refund_amount: amount to refund e.g. 810.0
    """
    db = load_db(DBFile.BOOKINGS)
    booking = db["bookings"].get(booking_id)

    if not booking:
        raise BookingError(
            message=f"Booking '{booking_id}' not found.",
            code="BOOKING_NOT_FOUND",
            recoverable=True
        )

    if booking["status"] != BookingStatus.CANCELLED:
        raise BookingError(
            message="Cannot process refund — booking is not cancelled yet.",
            code="BOOKING_NOT_CANCELLED",
            recoverable=False
        )

    if refund_amount <= 0:
        logger.info(f"no refund for booking {booking_id}")
        return {
            "status":     "success",
            "refund_id":  None,
            "amount":     0,
            "message":    "No refund applicable for this cancellation.",
            "eta_days":   0
        }

    refund_id = f"r_{booking_id}"

    # update refund status in bookings
    db["bookings"][booking_id]["refund_amount"] = refund_amount
    save_db(DBFile.BOOKINGS, db)

    logger.info(f"refund {refund_id} processed — amount: {refund_amount}")
    return {
        "status":    "success",
        "refund_id": refund_id,
        "amount":    refund_amount,
        "method":    "original_payment",
        "eta_days":  5
    }

