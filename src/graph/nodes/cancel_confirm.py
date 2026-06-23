from langgraph.types import interrupt
from src.config.constants import BookingStatus
from src.utils.date_utils import get_now
from src.utils.logger import get_logger
from src.api import services
from langchain_core.messages import AIMessage
from src.utils.id_cleaner import get_movie_title_by_id, get_theater_name_by_id
from src.utils.confirmation_classifier import classify_confirmation_input

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



    resolved_decision = classify_confirmation_input(decision)

    if resolved_decision == "Query":
        logger.info("cancellation interrupted by conversational query. Redirecting to planner.")
        return {"cancel_draft": None, "confirmed": False, "redirect_to_planner": True}

    if resolved_decision != "Approve":
        logger.info(f"cancellation rejected by user for booking {cancel_draft['booking_id']}")
        msg = AIMessage(content="Your cancellation request was rejected. The booking remains active.")
        return {"cancel_draft": None, "confirmed": False, "messages": [msg]}

    booking_id = cancel_draft["booking_id"]

    # Process cancel in Database
    try:
        cancelled_booking = services.cancel_booking(
            booking_id=booking_id,
            refund_amount=cancel_draft["refund_amount"],
            reason=cancel_draft.get("reason") or "User requested cancellation"
        )
    except Exception as e:
        logger.error(f"Failed to cancel booking {booking_id} in database: {e}", exc_info=True)
        err_msg = AIMessage(content="❌ **Cancellation Failed**\n\nSorry, we could not cancel your booking at this moment. Please try again.")
        return {"cancel_draft": None, "confirmed": False, "messages": [err_msg]}

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