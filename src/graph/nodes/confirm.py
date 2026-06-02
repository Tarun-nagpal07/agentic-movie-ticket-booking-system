from langgraph.types import interrupt
from src.utils.logger import get_logger
from src.db.json_store import load_db, save_db
from src.config.constants import DBFile, SeatStatus
from src.utils.date_utils import get_now

logger = get_logger(__name__)

def confirm_node(state: dict) -> dict:
    draft = state.get("booking_draft")

    if not draft:
        return state

    # pause here — user sees booking details and approves/rejects
    decision = interrupt({
        "message": "Confirm your booking?",
        "data":    draft,
        "options": ["Approve", "Reject"]
    })

    if decision != "Approve":
        logger.info(f"booking rejected by user")
        return {**state, "booking_draft": None, "confirmed": False}

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
    return {**state, "confirmed": True, "booking_draft": confirmed_draft}