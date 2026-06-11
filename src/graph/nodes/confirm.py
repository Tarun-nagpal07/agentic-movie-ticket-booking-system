from langgraph.types import interrupt
from src.utils.logger import get_logger
from src.db.json_store import load_db, save_db
from src.config.constants import DBFile, SeatStatus
from src.utils.date_utils import get_now

logger = get_logger(__name__)

def confirm_node(state: dict) -> dict:
    draft = state.get("booking_draft")

    if not draft:
        return {}

    # pause here — user sees booking details and approves/rejects
    decision = interrupt({
        "message": "Confirm your booking?",
        "data":    draft,
        "options": ["Approve", "Reject"]
    })

    from langchain_core.messages import AIMessage
    from src.utils.id_cleaner import get_movie_title_by_id, get_theater_name_by_id

    if decision not in ("Approve", "Reject"):
        logger.info("booking interrupted by conversational query. Redirecting to planner.")
        return {"booking_draft": None, "confirmed": False, "redirect_to_planner": True}

    if decision != "Approve":
        logger.info(f"booking rejected by user")
        msg = AIMessage(content="Your booking draft has been cancelled.")
        return {"booking_draft": None, "confirmed": False, "messages": [msg]}

    # write to JSON only after approval
    showtimes_db = load_db(DBFile.SHOWTIMES)
    bookings_db  = load_db(DBFile.BOOKINGS)

    confirmed_draft = {
        **draft,
        "status":    "confirmed",
        "booked_at": get_now()
    }


    bookings_db["bookings"][confirmed_draft["booking_id"]] = confirmed_draft
    save_db(DBFile.BOOKINGS, bookings_db)

    # flip seats
    tid, mid, sid = draft["theater_id"], draft["movie_id"], draft["show_id"]
    shows = showtimes_db["showtimes"][tid][mid]
    show_index = next(i for i, s in enumerate(shows) if s["show_id"] == sid)
    for seat in draft["seats"]:
        showtimes_db["showtimes"][tid][mid][show_index]["seats"][seat] = SeatStatus.BOOKED
    save_db(DBFile.SHOWTIMES, showtimes_db)

    logger.info(f"booking {draft['booking_id']} confirmed")

    movie_title = get_movie_title_by_id(confirmed_draft["movie_id"]) or "Movie"
    theater_name = get_theater_name_by_id(confirmed_draft["theater_id"]) or "Theater"
    seats_str = ", ".join(confirmed_draft["seats"])
    
    success_msg = AIMessage(content=f"🎉 **Booking Successful!**\n\n"
                                    f"Your booking has been confirmed.\n\n"
                                    f"**Booking Details:**\n"
                                    f"- **Movie:** {movie_title}\n"
                                    f"- **Theater:** {theater_name}\n"
                                    f"- **Screen:** {confirmed_draft['screen_name']} (Screen {confirmed_draft['screen_no']})\n"
                                    f"- **Date:** {confirmed_draft['show_date']}\n"
                                    f"- **Time:** {confirmed_draft['show_time']}\n"
                                    f"- **Seats:** {seats_str}\n"
                                    f"- **Total Paid:** ₹{confirmed_draft['total_price']}")

    return {"confirmed": True, "booking_draft": confirmed_draft, "last_booking_id": confirmed_draft["booking_id"], "messages": [success_msg]}