from langchain.tools import tool
from src.db.json_store import load_db
from src.config.constants import DBFile, BookingStatus, Limits
from src.utils.errors import handle_errors, ToolError
from src.utils.logger import get_logger
from src.schemas.booking import (
    GetBookingRequest,
    GetBookingsByStatusRequest
)

logger = get_logger(__name__)


def make_history_tools(user_id: str):
    """
    Factory that returns history tools bound to a specific user_id.
    Call this inside history_node so each invocation gets the correct user context.
    """

    @tool("get_booking_history")
    @handle_errors(error_class=ToolError)
    def get_booking_history(limit: int = Limits.HISTORY_DEFAULT_LIMIT) -> dict:
        """
        Get past bookings for a user.
        Use when user asks about their booking history, past movies, or spent amount.

        Args:
            limit: max number of bookings to return (default 10)
        """
        db = load_db(DBFile.BOOKINGS)

        all_bookings = [
            b for b in db["bookings"].values()
            if b["user_id"] == user_id
        ]

        if not all_bookings:
            raise ToolError(
                message=f"No booking history found for user '{user_id}'.",
                code="NO_HISTORY_FOUND",
                recoverable=True
            )

        # sort by booked_at descending — most recent first
        sorted_bookings = sorted(
            all_bookings,
            key=lambda b: b["booked_at"],
            reverse=True
        )[:limit]

        logger.info(f"found {len(sorted_bookings)} bookings for user {user_id}")
        return {
            "status":   "success",
            "total":    len(all_bookings),
            "returned": len(sorted_bookings),
            "bookings": sorted_bookings
        }

    @tool("get_booking_by_id", args_schema=GetBookingRequest)
    @handle_errors(error_class=ToolError)
    def get_booking_by_id(booking_id: str) -> dict:
        """
        Get a single booking by its ID.
        Use when user asks about a specific booking or wants to cancel one.

        Args:
            booking_id: booking ID e.g. "b_001"
        """
        db = load_db(DBFile.BOOKINGS)
        booking = db["bookings"].get(booking_id)

        if not booking:
            raise ToolError(
                message=f"No booking found for booking_id: '{booking_id}'.",
                code="BOOKING_NOT_FOUND",
                recoverable=True
            )

        logger.info(f"booking {booking_id} fetched")
        return {"status": "success", "booking": booking}

    @tool("get_last_booking")
    @handle_errors(error_class=ToolError)
    def get_last_booking() -> dict:
        """
        Get the most recent confirmed booking for a user.
        Use when user says 'rebook my last booking' or 'same seats as last time'.
        """
        db = load_db(DBFile.BOOKINGS)

        confirmed = [
            b for b in db["bookings"].values()
            if b["user_id"] == user_id
            and b["status"] == BookingStatus.CONFIRMED
        ]

        if not confirmed:
            raise ToolError(
                message=f"No confirmed bookings found for user '{user_id}'.",
                code="NO_CONFIRMED_BOOKING",
                recoverable=True
            )

        last = max(confirmed, key=lambda b: b["booked_at"])

        logger.info(f"last booking for user {user_id} is {last['booking_id']}")
        return {
            "status":  "success",
            "booking": last
        }

    @tool("get_bookings_by_status", args_schema=GetBookingsByStatusRequest)
    @handle_errors(error_class=ToolError)
    def get_bookings_by_status(status: str) -> dict:
        """
        Get all bookings filtered by status for a user.
        Use when user asks specifically about confirmed or cancelled bookings.

        Args:
            status: "confirmed" or "cancelled"
        """
        if status not in [BookingStatus.CONFIRMED, BookingStatus.CANCELLED]:
            raise ToolError(
                message=f"Invalid status '{status}'. Use 'confirmed' or 'cancelled'.",
                code="INVALID_STATUS",
                recoverable=True
            )

        db = load_db(DBFile.BOOKINGS)

        filtered = [
            b for b in db["bookings"].values()
            if b["user_id"] == user_id
            and b["status"] == status
        ]

        if not filtered:
            raise ToolError(
                message=f"No {status} bookings found for user '{user_id}'.",
                code="NO_BOOKINGS_FOUND",
                recoverable=True
            )

        sorted_bookings = sorted(filtered, key=lambda b: b["booked_at"], reverse=True)

        logger.info(f"found {len(sorted_bookings)} {status} bookings for user {user_id}")
        return {
            "status":   "success",
            "bookings": sorted_bookings
        }

    return [
        get_booking_history,
        get_booking_by_id,
        get_last_booking,
        get_bookings_by_status,
    ]