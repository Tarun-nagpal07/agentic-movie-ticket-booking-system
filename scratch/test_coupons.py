import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.db.postgres import init_db, get_db_cursor
from src.api import services
from src.tools.offer_tools import list_offers
from src.tools.booking_tools import book_tickets
from langchain_core.runnables import RunnableConfig

def run_tests():
    print("=== INITIALIZING DATABASE WITH NEW SCHEMA ===")
    init_db(force=True)
    print("Database re-seeded successfully.\n")

    print("=== VERIFYING ACTIVE COUPONS ===")
    coupons = services.get_active_coupons()
    print(f"Found {len(coupons)} active coupons:")
    for c in coupons:
        print(f"- {c['coupon_code']}: {c['description']} (Brand: {c['theater_brand']}, Movie: {c['movie_id']})")
    print()

    print("=== TESTING RETRIEVAL BY CODE ===")
    film100 = services.get_coupon_by_code("FILM100")
    assert film100 is not None, "FILM100 coupon not found"
    print(f"Successfully retrieved FILM100: {film100}\n")

    # Fetch a show and seats to perform a test booking
    with get_db_cursor() as cur:
        # Find a show at PVR
        cur.execute("""
            SELECT s.show_id, s.price, t.name, t.theater_id, s.movie_id
            FROM showtimes s
            JOIN theaters t ON s.theater_id = t.theater_id
            WHERE t.name ILIKE '%PVR%'
            LIMIT 1;
        """)
        pvr_show = cur.fetchone()
        
        # Find a show at INOX
        cur.execute("""
            SELECT s.show_id, s.price, t.name, t.theater_id, s.movie_id
            FROM showtimes s
            JOIN theaters t ON s.theater_id = t.theater_id
            WHERE t.name ILIKE '%INOX%'
            LIMIT 1;
        """)
        inox_show = cur.fetchone()

    if not pvr_show or not inox_show:
        print("Error: Could not find both PVR and INOX shows in seeded data.")
        return

    pvr_show_id, pvr_price, pvr_tname, pvr_tid, pvr_mid = pvr_show
    inox_show_id, inox_price, inox_tname, inox_tid, inox_mid = inox_show

    # Get available seats
    with get_db_cursor() as cur:
        cur.execute("SELECT seat_label FROM seats WHERE show_id = %s AND status = 'available' LIMIT 2;", (pvr_show_id,))
        pvr_seats = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT seat_label FROM seats WHERE show_id = %s AND status = 'available' LIMIT 2;", (inox_show_id,))
        inox_seats = [r[0] for r in cur.fetchall()]

    print(f"PVR show: {pvr_tname} ({pvr_show_id}), Price: {pvr_price}, Seats: {pvr_seats}")
    print(f"INOX show: {inox_tname} ({inox_show_id}), Price: {inox_price}, Seats: {inox_seats}\n")

    # Test User ID (mapped in seed.py)
    user_id = "00000000-0000-0000-0000-000000000001" # u1

    print("=== TESTING BRAND RESTRICTIONS (PVR coupon on INOX show) ===")
    try:
        # PVR50 is restricted to PVR theaters
        services.create_booking(user_id, inox_show_id, [inox_seats[0]], coupon_code="PVR50")
        print("❌ FAILED: Created PVR booking on INOX show without brand exception.")
    except ValueError as e:
        print(f"✅ PASSED: Correctly raised error: {e}\n")

    print("=== TESTING VALID BOOKING WITH PVR COUPON ON PVR SHOW ===")
    try:
        original_total = pvr_price * len(pvr_seats)
        booking = services.create_booking(user_id, pvr_show_id, pvr_seats, coupon_code="PVR50")
        print(f"Booking created with ID: {booking['booking_id']}")
        print(f"Original total: ₹{original_total}, Discounted total: ₹{booking['total_price']}")
        print(f"Coupon code stored: {booking.get('coupon_code')}")
        assert booking['total_price'] == original_total - 50, "PVR50 discount not calculated correctly"
        print("✅ PASSED: Coupon applied and discounted price stored successfully.\n")
    except Exception as e:
        print(f"❌ FAILED: Error: {e}\n")

    print("=== TESTING DUPLICATE COUPON USE BLOCK ===")
    try:
        # Try to use PVR50 again for the same user
        services.create_booking(user_id, pvr_show_id, [pvr_seats[0]], coupon_code="PVR50")
        print("❌ FAILED: Allowed duplicate use of single-use coupon PVR50.")
    except ValueError as e:
        print(f"✅ PASSED: Correctly blocked duplicate use: {e}\n")

    print("=== TESTING LIST_OFFERS TOOL ===")
    config = RunnableConfig(configurable={"user_id": user_id, "city": "ahmedabad"})
    
    # List offers without filters
    res = list_offers.invoke({"movie_id": None, "theater_id": None}, config=config)
    print("All applicable offers for user:")
    for offer in res["offers"]:
        print(f"- Code: {offer['coupon_code']} | Status: {offer['status']} | Description: {offer['description']}")
    print()

    # Verify that PVR50 shows as "Already Used"
    used_coupon = next((o for o in res["offers"] if o["coupon_code"] == "PVR50"), None)
    assert used_coupon is not None and used_coupon["status"] == "Already Used", "PVR50 status should be 'Already Used'"
    print("✅ PASSED: list_offers tool correctly shows coupon usage status.\n")

    # Test list_offers filters
    res_pvr = list_offers.invoke({"theater_id": pvr_tid}, config=config)
    print(f"Offers for PVR theater {pvr_tname}:")
    for offer in res_pvr["offers"]:
        print(f"- Code: {offer['coupon_code']} | Description: {offer['description']}")
    print()
    
    res_inox = list_offers.invoke({"theater_id": inox_tid}, config=config)
    print(f"Offers for INOX theater {inox_tname}:")
    for offer in res_inox["offers"]:
        print(f"- Code: {offer['coupon_code']} | Description: {offer['description']}")
    print()

    print("=== TESTING BOOK_TICKETS TOOL WITH COUPON ===")
    # Reset status of the PVR seat to test booking draft
    with get_db_cursor() as cur:
        cur.execute("UPDATE seats SET status = 'available' WHERE show_id = %s AND seat_label IN (%s, %s);", (pvr_show_id, pvr_seats[0], pvr_seats[1]))
    
    draft_res = book_tickets.invoke({
        "show_id": pvr_show_id,
        "seats": pvr_seats,
        "num_tickets": len(pvr_seats),
        "coupon_code": "FILM100"
    }, config=config)
    
    assert draft_res["status"] == "draft", "book_tickets did not return draft"
    draft = draft_res["booking_draft"]
    print("Draft details:")
    print(f"- Coupon Code: {draft['coupon_code']}")
    print(f"- Discount Amount: ₹{draft['discount_amount']}")
    print(f"- Total Price: ₹{draft['total_price']}")
    assert draft['coupon_code'] == "FILM100"
    assert draft['discount_amount'] == 100.0
    print("✅ PASSED: book_tickets tool validates and drafts discounts correctly.\n")

if __name__ == "__main__":
    run_tests()
