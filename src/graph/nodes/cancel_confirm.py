from langgraph.types import interrupt
from src.db.json_store import load_db, save_db
from src.config.constants import DBFile, BookingStatus, SeatStatus
from src.utils.date_utils import get_now
from src.utils.logger import get_logger

logger = get_logger(__name__)


def cancel_confirm_node(state: dict) -> dict:
    cancel_draft = state.get("cancel_draft")

    if not cancel_draft or cancel_draft.get("status") == BookingStatus.CANCELLED:
        return {}

    # pause — show user what they're cancelling and refund amount
    decision = interrupt({
        "message": f"Cancel booking for {cancel_draft['show_date']} at {cancel_draft['show_time']}? "
                   f"Refund: ₹{cancel_draft['refund_amount']} ({cancel_draft['refund_message']})",
        "data":    cancel_draft,
        "options": ["Approve", "Reject"]
    })

    from langchain_core.messages import AIMessage
    from src.utils.id_cleaner import get_movie_title_by_id, get_theater_name_by_id
    from src.utils.confirmation_classifier import classify_confirmation_input

    resolved_decision = classify_confirmation_input(decision)

    if resolved_decision == "Query":
        logger.info("cancellation interrupted by conversational query. Redirecting to planner.")
        return {"cancel_draft": None, "confirmed": False, "redirect_to_planner": True}

    if resolved_decision != "Approve":
        logger.info(f"cancellation rejected by user for booking {cancel_draft['booking_id']}")
        msg = AIMessage(content="Your cancellation request was rejected. The booking remains active.")
        return {"cancel_draft": None, "confirmed": False, "messages": [msg]}

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

    movie_title = get_movie_title_by_id(cancel_draft["movie_id"]) or "Movie"
    theater_name = get_theater_name_by_id(cancel_draft["theater_id"]) or "Theater"
    seats_str = ", ".join(cancel_draft["seats"])

    success_msg = AIMessage(content=f"🗑️ **Cancellation Successful!**\n\n"
                                    f"Your booking has been cancelled successfully.\n\n"
                                    f"**Cancellation Details:**\n"
                                    f"- **Movie:** {movie_title}\n"
                                    f"- **Theater:** {theater_name}\n"
                                    f"- **Date:** {cancel_draft['show_date']}\n"
                                    f"- **Time:** {cancel_draft['show_time']}\n"
                                    f"- **Seats:** {seats_str}\n"
                                    f"- **Refund Amount:** ₹{cancel_draft['refund_amount']} ({cancel_draft['refund_message']})")

    return {
        "confirmed":    True,
        "cancel_draft": {
            **cancel_draft,
            "status":       BookingStatus.CANCELLED,
            "cancelled_at": get_now()
        },
        "messages": [success_msg]
    }