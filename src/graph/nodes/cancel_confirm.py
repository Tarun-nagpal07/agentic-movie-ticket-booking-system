from langgraph.types import interrupt
from src.db.json_store import load_db, save_db
from src.config.constants import DBFile, BookingStatus, SeatStatus
from src.utils.date_utils import get_now
from src.utils.logger import get_logger

logger = get_logger(__name__)


def cancel_confirm_node(state: dict) -> dict:
    cancel_draft = state.get("cancel_draft")

    if not cancel_draft:
        return {}

    # pause — show user what they're cancelling and refund amount
    decision = interrupt({
        "message": f"Cancel booking for {cancel_draft['show_date']} at {cancel_draft['show_time']}? "
                   f"Refund: ₹{cancel_draft['refund_amount']} ({cancel_draft['refund_message']})",
        "data":    cancel_draft,
        "options": ["Approve", "Reject"]
    })

    if decision != "Approve":
        logger.info(f"cancellation rejected by user for booking {cancel_draft['booking_id']}")
        return {"cancel_draft": None, "confirmed": False}

    bookings_db  = load_db(DBFile.BOOKINGS)
    showtimes_db = load_db(DBFile.SHOWTIMES)

    booking_id = cancel_draft["booking_id"]

    # update booking status
    bookings_db["bookings"][booking_id] = {
        **bookings_db["bookings"][booking_id],
        "status":       BookingStatus.CANCELLED,
        "cancelled_at": get_now(),
        "refund_amount": cancel_draft["refund_amount"]
    }
    save_db(DBFile.BOOKINGS, bookings_db)

    # flip seats back to available
    tid, mid, sid = cancel_draft["theater_id"], cancel_draft["movie_id"], cancel_draft["show_id"]
    shows      = showtimes_db["showtimes"][tid][mid]
    show_index = next(i for i, s in enumerate(shows) if s["show_id"] == sid)

    for seat in cancel_draft["seats"]:
        showtimes_db["showtimes"][tid][mid][show_index]["seats"][seat] = SeatStatus.AVAILABLE

    save_db(DBFile.SHOWTIMES, showtimes_db)

    logger.info(f"booking {booking_id} cancelled — refund: {cancel_draft['refund_amount']}")
    return {
        "confirmed":    True,
        "cancel_draft": {
            **cancel_draft,
            "status":       BookingStatus.CANCELLED,
            "cancelled_at": get_now()
        }
    }