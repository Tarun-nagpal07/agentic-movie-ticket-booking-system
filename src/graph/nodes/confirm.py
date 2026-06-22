from langgraph.types import interrupt
from src.utils.logger import get_logger
from src.api import services
from src.utils.date_utils import get_now

logger = get_logger(__name__)

def confirm_node(state: dict) -> dict:
    draft = state.get("booking_draft")

    if not draft or draft.get("status") == "confirmed":
        return {}

    # pause here — user sees booking details and approves/rejects
    decision = interrupt({
        "message": "Confirm your booking?",
        "data":    draft,
        "options": ["Approve", "Reject"]
    })

    from langchain_core.messages import AIMessage
    from src.utils.id_cleaner import get_movie_title_by_id, get_theater_name_by_id
    from src.utils.confirmation_classifier import classify_confirmation_input

    resolved_decision = classify_confirmation_input(decision)

    if resolved_decision == "Query":
        logger.info("booking interrupted by conversational query. Redirecting to planner.")
        return {"booking_draft": None, "confirmed": False, "redirect_to_planner": True}

    if resolved_decision != "Approve":
        logger.info(f"booking rejected by user")
        msg = AIMessage(content="Your booking draft has been cancelled.")
        return {"booking_draft": None, "confirmed": False, "messages": [msg]}

    # write to Database only after approval
    try:
        confirmed_booking = services.create_booking(
            user_id=draft["user_id"],
            show_id=draft["show_id"],
            seats=draft["seats"],
            booking_id=draft["booking_id"],
            coupon_code=draft.get("coupon_code")
        )
    except ValueError as ve:
        logger.error(f"Validation failed to confirm booking {draft.get('booking_id')}: {ve}")
        err_msg = AIMessage(content=f"❌ **Booking Failed**\n\nSorry, we could not confirm your booking: {str(ve)}")
        return {"booking_draft": None, "confirmed": False, "messages": [err_msg]}
    except Exception as e:
        logger.error(f"Failed to confirm booking {draft.get('booking_id')}: {e}", exc_info=True)
        err_msg = AIMessage(content="❌ **Booking Failed**\n\nSorry, we could not confirm your booking because one or more seats are no longer available or the showtime is invalid.")
        return {"booking_draft": None, "confirmed": False, "messages": [err_msg]}

    logger.info(f"booking {draft['booking_id']} confirmed")

    movie_title = get_movie_title_by_id(confirmed_booking["movie_id"]) or "Movie"
    theater_name = get_theater_name_by_id(confirmed_booking["theater_id"]) or "Theater"
    seats_str = ", ".join(confirmed_booking["seats"])
    
    success_msg = AIMessage(content=f"🎉 **Booking Successful!**\n\n"
                                    f"Your booking has been confirmed.\n\n"
                                    f"**Booking Details:**\n"
                                    f"- **Movie:** {movie_title}\n"
                                    f"- **Theater:** {theater_name}\n"
                                    f"- **Screen:** {confirmed_booking['screen_name']} (Screen {confirmed_booking['screen_no']})\n"
                                    f"- **Date:** {confirmed_booking['show_date']}\n"
                                    f"- **Time:** {confirmed_booking['show_time']}\n"
                                    f"- **Seats:** {seats_str}\n"
                                    f"- **Total Paid:** ₹{confirmed_booking['total_price']}")

    return {"confirmed": True, "booking_draft": confirmed_booking, "last_booking_id": confirmed_booking["booking_id"], "messages": [success_msg]}