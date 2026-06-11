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
from src.utils.id_cleaner import get_movie_title_by_id, get_theater_name_by_id

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

    if not booking.get("movie_title") or booking.get("movie_title") == "Movie":
        booking["movie_title"] = get_movie_title_by_id(booking.get("movie_id")) or "Movie"
    if not booking.get("theater_name") or booking.get("theater_name") == "Theater":
        booking["theater_name"] = get_theater_name_by_id(booking.get("theater_id")) or "Theater"

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
        "movie_title":   booking.get("movie_title") or get_movie_title_by_id(booking.get("movie_id")) or "Movie",
        "theater_id":    booking["theater_id"],
        "theater_name":  booking.get("theater_name") or get_theater_name_by_id(booking.get("theater_id")) or "Theater",
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


def make_cancellation_tools(user_id: str):
    """
    Factory that returns cancellation tools bound to a specific user_id.
    This gives get_last_booking access to user_id.
    """
    @tool("get_last_booking")
    @handle_errors(error_class=ToolError)
    def get_last_booking() -> dict:
        """
        Get the most recently confirmed booking for the current user.
        Use when user says 'cancel my last booking', 'cancel that booking', or 'cancel my booking'
        and no specific booking ID is available in context.
        """
        db = load_db(DBFile.BOOKINGS)
        confirmed = [
            b for b in db["bookings"].values()
            if b["user_id"] == user_id and b["status"] == BookingStatus.CONFIRMED
        ]
        if not confirmed:
            raise ToolError(
                message=f"No confirmed bookings found for user.",
                code="NO_CONFIRMED_BOOKING",
                recoverable=True
            )
        last = max(confirmed, key=lambda b: b["booked_at"])
        # Enrich names
        if not last.get("movie_title") or last["movie_title"] == "Movie":
            last["movie_title"] = get_movie_title_by_id(last.get("movie_id")) or "Movie"
        if not last.get("theater_name") or last["theater_name"] == "Theater":
            last["theater_name"] = get_theater_name_by_id(last.get("theater_id")) or "Theater"
        
        logger.info(f"last booking for user {user_id} is {last['booking_id']}")
        return {"status": "success", "booking": last}

    @tool("get_booking_by_movie")
    @handle_errors(error_class=ToolError)
    def get_booking_by_movie(movie_name: str) -> dict:
        """
        Get booking details matching a movie name for the current user.
        Use when user asks to cancel their booking for a specific movie (e.g. 'cancel my ticket for Interstellar').

        Args:
            movie_name: the name of the movie (e.g., 'Interstellar', 'Pathaan')
        """
        from src.tools.booking_tools import _resolve_movie_name_to_id
        movie_id = _resolve_movie_name_to_id(movie_name)
        if not movie_id:
            raise ToolError(
                message=f"Could not find any movie matching '{movie_name}'.",
                code="MOVIE_NOT_FOUND",
                recoverable=True
            )

        db = load_db(DBFile.BOOKINGS)
        bookings = [
            b for b in db["bookings"].values()
            if b["user_id"] == user_id
            and b["movie_id"] == movie_id
            and b["status"] == BookingStatus.CONFIRMED
        ]

        if not bookings:
            raise ToolError(
                message=f"No confirmed bookings found for movie '{movie_name}'.",
                code="NO_BOOKINGS_FOUND",
                recoverable=True
            )

        # Enrich names
        for last in bookings:
            if not last.get("movie_title") or last["movie_title"] == "Movie":
                last["movie_title"] = get_movie_title_by_id(last.get("movie_id")) or "Movie"
            if not last.get("theater_name") or last["theater_name"] == "Theater":
                last["theater_name"] = get_theater_name_by_id(last.get("theater_id")) or "Theater"

        # Sort by booked_at descending so the most recent is first
        bookings.sort(key=lambda b: b["booked_at"], reverse=True)

        logger.info(f"found {len(bookings)} bookings for movie {movie_name} (ID: {movie_id})")
        return {
            "status": "success",
            "booking": bookings[0],
            "matches": bookings
        }

    return [get_booking_by_id, prepare_cancellation, process_refund, get_last_booking, get_booking_by_movie]


