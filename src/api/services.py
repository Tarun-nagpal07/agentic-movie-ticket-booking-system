import json
import uuid
from datetime import datetime, date, time
from functools import lru_cache
from src.db.postgres import get_db_cursor
from src.config.constants import SeatStatus, BookingStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Seats in-memory cache to avoid database hit on unchanged seat statuses
_seats_cache = {}

# --- Helper Converters ---

def movie_row_to_dict(row):
    if not row:
        return None
    return {
        "movie_id": row[0],
        "title": row[1],
        "genre": row[2] if isinstance(row[2], list) else [],
        "language": row[3],
        "duration_min": row[4],
        "rating": row[5],
        "cast": row[6] if isinstance(row[6], list) else [],
        "description": row[7]
    }

def theater_row_to_dict(row):
    if not row:
        return None
    return {
        "theater_id": row[0],
        "name": row[1],
        "city": row[2],
        "address": row[3],
        "latitude": row[4],
        "longitude": row[5],
        "amenities": row[6] if isinstance(row[6], list) else [],
        "parking": row[7]
    }

def showtime_row_to_dict(row):
    if not row:
        return None
    show_date_str = row[5].strftime("%Y-%m-%d") if isinstance(row[5], (date, datetime)) else str(row[5])
    
    if isinstance(row[6], time):
        show_time_str = row[6].strftime("%H:%M")
    elif isinstance(row[6], str):
        show_time_str = row[6][:5]
    else:
        # timedelta
        total_seconds = int(row[6].total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        show_time_str = f"{hours:02d}:{minutes:02d}"
        
    return {
        "show_id": row[0],
        "movie_id": row[1],
        "theater_id": row[2],
        "screen_no": row[3],
        "screen_name": row[4],
        "date": show_date_str,
        "time": show_time_str,
        "format": row[7],
        "price": row[8],
        "seat_types": row[9] if isinstance(row[9], dict) else {}
    }

def user_row_to_dict(row):
    if not row:
        return None
    return {
        "user_id": str(row[0]),
        "name": row[1],
        "email": row[2],
        "password_hash": row[3],
        "phone": row[4],
        "city": row[5],
        "latitude": row[6],
        "longitude": row[7],
        "favorite_genres": row[8] if isinstance(row[8], list) else [],
        "preferred_theaters": row[9] if isinstance(row[9], list) else [],
        "preferred_seat_type": row[10],
        "preferred_format": row[11],
        "language_pref": row[12]
    }

def get_booking_seats_and_type(booking_id: str) -> tuple[list[str], str]:
    with get_db_cursor() as cur:
        cur.execute("SELECT seat_label, seat_type FROM booking_seats WHERE booking_id = %s;", (booking_id,))
        rows = cur.fetchall()
        seats = [r[0] for r in rows]
        seat_type = rows[0][1] if rows else "standard"
        return seats, seat_type

def booking_row_to_dict(row):
    if not row:
        return None
    booking_id = row[0]
    seats, seat_type = get_booking_seats_and_type(booking_id)
    
    show_date_str = row[7].strftime("%Y-%m-%d") if isinstance(row[7], (date, datetime)) else str(row[7])
    
    if isinstance(row[8], time):
        show_time_str = row[8].strftime("%H:%M")
    elif isinstance(row[8], str):
        show_time_str = row[8][:5]
    else:
        total_seconds = int(row[8].total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        show_time_str = f"{hours:02d}:{minutes:02d}"
        
    booked_at_str = row[16].isoformat() if row[16] else ""
    cancelled_at_str = row[17].isoformat() if row[17] else None
    
    from src.utils.id_cleaner import get_movie_title_by_id, get_theater_name_by_id
    movie_title = get_movie_title_by_id(row[2]) or "Movie"
    theater_name = get_theater_name_by_id(row[3]) or "Theater"

    return {
        "booking_id": booking_id,
        "user_id": str(row[1]) if row[1] else None,
        "movie_id": row[2],
        "movie_title": movie_title,
        "theater_id": row[3],
        "theater_name": theater_name,
        "screen_no": row[4],
        "screen_name": row[5],
        "show_id": row[6],
        "show_date": show_date_str,
        "show_time": show_time_str,
        "format": row[9],
        "seats": seats,
        "seat_type": seat_type,
        "num_tickets": row[10],
        "price_per_ticket": row[11],
        "total_price": row[12],
        "status": row[13],
        "refund_amount": row[14],
        "reason": row[15],
        "booked_at": booked_at_str,
        "cancelled_at": cancelled_at_str,
        "coupon_code": row[18] if len(row) > 18 else None
    }

# --- Movie Services ---

@lru_cache(maxsize=1)
def get_movies() -> list[dict]:
    with get_db_cursor() as cur:
        cur.execute("SELECT movie_id, title, genre, language, duration_min, rating, cast_members, description FROM movies;")
        return [movie_row_to_dict(r) for r in cur.fetchall()]

@lru_cache(maxsize=128)
def get_movie_by_id(movie_id: str) -> dict | None:
    with get_db_cursor() as cur:
        cur.execute("SELECT movie_id, title, genre, language, duration_min, rating, cast_members, description FROM movies WHERE movie_id = %s;", (movie_id,))
        return movie_row_to_dict(cur.fetchone())

@lru_cache(maxsize=128)
def search_movies(query: str) -> list[dict]:
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT movie_id, title, genre, language, duration_min, rating, cast_members, description 
            FROM movies 
            WHERE title ILIKE %s OR description ILIKE %s OR language ILIKE %s;
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))
        return [movie_row_to_dict(r) for r in cur.fetchall()]

# --- Theater Services ---

@lru_cache(maxsize=32)
def get_theaters_by_city(city: str) -> list[dict]:
    with get_db_cursor() as cur:
        cur.execute("SELECT theater_id, name, city, address, latitude, longitude, amenities, parking FROM theaters WHERE LOWER(city) = %s;", (city.lower(),))
        return [theater_row_to_dict(r) for r in cur.fetchall()]

@lru_cache(maxsize=64)
def get_theater_by_id(theater_id: str) -> dict | None:
    with get_db_cursor() as cur:
        cur.execute("SELECT theater_id, name, city, address, latitude, longitude, amenities, parking FROM theaters WHERE theater_id = %s;", (theater_id,))
        theater = theater_row_to_dict(cur.fetchone())
        if theater:
            theater["screens"] = get_screens_by_theater(theater_id)
        return theater

@lru_cache(maxsize=64)
def get_screens_by_theater(theater_id: str) -> list[dict]:
    with get_db_cursor() as cur:
        cur.execute("SELECT screen_no, name, format, capacity FROM screens WHERE theater_id = %s;", (theater_id,))
        return [{
            "screen_no": r[0],
            "name": r[1],
            "format": r[2],
            "capacity": r[3]
        } for r in cur.fetchall()]

# --- Showtime Services ---

@lru_cache(maxsize=256)
def get_showtimes(theater_id: str, movie_id: str, show_date: str) -> list[dict]:
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT show_id, movie_id, theater_id, screen_no, screen_name, show_date, show_time, format, price, seat_types 
            FROM showtimes 
            WHERE theater_id = %s AND movie_id = %s AND show_date = %s
            ORDER BY show_time;
        """, (theater_id, movie_id, show_date))
        return [showtime_row_to_dict(r) for r in cur.fetchall()]

@lru_cache(maxsize=128)
def get_showtimes_by_theater_and_date(theater_id: str, show_date: str) -> list[dict]:
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT show_id, movie_id, theater_id, screen_no, screen_name, show_date, show_time, format, price, seat_types 
            FROM showtimes 
            WHERE theater_id = %s AND show_date = %s
            ORDER BY show_time;
        """, (theater_id, show_date))
        return [showtime_row_to_dict(r) for r in cur.fetchall()]

@lru_cache(maxsize=256)
def get_show_details(show_id: str) -> dict | None:
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT show_id, movie_id, theater_id, screen_no, screen_name, show_date, show_time, format, price, seat_types 
            FROM showtimes 
            WHERE show_id = %s;
        """, (show_id,))
        return showtime_row_to_dict(cur.fetchone())

# --- Seat Services ---

def get_show_seats(show_id: str) -> dict:
    if show_id in _seats_cache:
        return _seats_cache[show_id]
    with get_db_cursor() as cur:
        cur.execute("SELECT seat_label, status FROM seats WHERE show_id = %s ORDER BY seat_label;", (show_id,))
        seats = {r[0]: r[1] for r in cur.fetchall()}
        _seats_cache[show_id] = seats
        return seats

# --- User Services ---

def get_user_by_id(user_id: str, include_bookings: bool = True) -> dict | None:
    try:
        # check if valid UUID format, if not try mapping it
        uuid.UUID(user_id)
    except ValueError:
        from src.db.seed import get_user_uuid
        user_id = get_user_uuid(user_id)
        
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT id, name, email, password_hash, phone, city, latitude, longitude, 
                   favorite_genres, preferred_theaters, preferred_seat_type, preferred_format, language_pref 
            FROM users WHERE id = %s;
        """, (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        user_dict = user_row_to_dict(row)
        if include_bookings:
            user_dict["booking_history"] = get_user_bookings(user_id)
        return user_dict

def get_user_by_email(email: str) -> dict | None:
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT id, name, email, password_hash, phone, city, latitude, longitude, 
                   favorite_genres, preferred_theaters, preferred_seat_type, preferred_format, language_pref 
            FROM users WHERE LOWER(email) = %s;
        """, (email.lower(),))
        row = cur.fetchone()
        if not row:
            return None
        return user_row_to_dict(row)

def create_user(name: str, email: str, password_hash: str, phone: str, city: str, latitude: float, longitude: float) -> dict:
    user_id = str(uuid.uuid4())
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO users (id, name, email, password_hash, phone, city, latitude, longitude, favorite_genres, preferred_theaters)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '[]'::jsonb, '[]'::jsonb)
            RETURNING id, name, email, phone, city, latitude, longitude;
        """, (user_id, name, email, password_hash, phone, city, latitude, longitude))
        row = cur.fetchone()
        return {
            "user_id": str(row[0]),
            "name": row[1],
            "email": row[2],
            "phone": row[3],
            "city": row[4],
            "latitude": row[5],
            "longitude": row[6]
        }

def update_user_preferences(user_id: str, preferences: dict) -> None:
    try:
        uuid.UUID(user_id)
    except ValueError:
        from src.db.seed import get_user_uuid
        user_id = get_user_uuid(user_id)

    # We fetch existing, merge them
    user = get_user_by_id(user_id, include_bookings=False)
    if not user:
        logger.error(f"User {user_id} not found to update preferences.")
        return
        
    fav_genres = preferences.get("favorite_genres", user.get("favorite_genres", []))
    pref_theaters = preferences.get("preferred_theaters", user.get("preferred_theaters", []))
    pref_seat = preferences.get("preferred_seat_type", user.get("preferred_seat_type"))
    pref_format = preferences.get("preferred_format", user.get("preferred_format"))
    lang_pref = preferences.get("language_pref", user.get("language_pref", "English"))
    
    with get_db_cursor() as cur:
        cur.execute("""
            UPDATE users 
            SET favorite_genres = %s, preferred_theaters = %s, preferred_seat_type = %s, 
                preferred_format = %s, language_pref = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (json.dumps(fav_genres), json.dumps(pref_theaters), pref_seat, pref_format, lang_pref, user_id))

# --- Booking Services ---

def create_booking(user_id: str, show_id: str, seats: list[str], booking_id: str = None, coupon_code: str = None) -> dict:
    """Atomic booking of seats in a transaction."""
    try:
        uuid.UUID(user_id)
    except ValueError:
        from src.db.seed import get_user_uuid
        user_id = get_user_uuid(user_id)

    if not booking_id:
        booking_id = f"b_{uuid.uuid4().hex[:6]}"

    # We obtain the database cursor and run everything in ONE single transaction (get_db_cursor handles commit/rollback)
    with get_db_cursor() as cur:
        # 1. Get show details first
        cur.execute("""
            SELECT movie_id, theater_id, screen_no, screen_name, show_date, show_time, format, price, seat_types 
            FROM showtimes WHERE show_id = %s;
        """, (show_id,))
        show_row = cur.fetchone()
        if not show_row:
            raise ValueError(f"Show {show_id} not found.")
            
        movie_id, theater_id, screen_no, screen_name, show_date, show_time, format, price, seat_types = show_row
        
        # 2. Validate and apply coupon if provided
        actual_coupon_code = None
        discount_amount = 0.0
        original_total = price * len(seats)
        total_price = original_total

        if coupon_code:
            coupon = get_coupon_by_code(coupon_code)
            if not coupon or not coupon["is_active"]:
                raise ValueError("Invalid or inactive coupon code.")
            if has_user_used_coupon(user_id, coupon["coupon_code"]):
                raise ValueError("You have already used this coupon code. You cannot use it again.")
            
            # Movie restriction
            if coupon["movie_id"] and coupon["movie_id"] != movie_id:
                raise ValueError("This coupon is not valid for the selected movie.")
            
            # Theater restriction
            if coupon["theater_id"] and coupon["theater_id"] != theater_id:
                raise ValueError("This coupon is not valid for the selected theater.")
            
            # Theater brand restriction (case-insensitive check against theater name)
            if coupon["theater_brand"]:
                theater = get_theater_by_id(theater_id)
                if not theater or coupon["theater_brand"].lower() not in theater["name"].lower():
                    raise ValueError(f"This coupon is only valid at {coupon['theater_brand']} theaters.")
            
            # Calculate discount
            if coupon["discount_type"] == "flat":
                discount_amount = coupon["discount_value"]
            elif coupon["discount_type"] == "percent":
                discount_amount = original_total * (coupon["discount_value"] / 100.0)
            
            discount_amount = min(discount_amount, original_total)
            total_price = int(original_total - discount_amount)
            actual_coupon_code = coupon["coupon_code"]

        # 3. Lock seats FOR UPDATE to prevent race conditions
        seat_placeholders = ", ".join(["%s"] * len(seats))
        cur.execute(f"""
            SELECT seat_label, status 
            FROM seats 
            WHERE show_id = %s AND seat_label IN ({seat_placeholders}) 
            FOR UPDATE;
        """, [show_id] + list(seats))
        locked_seats = cur.fetchall()
        
        # Verify seats exist and are available
        seat_status_map = {r[0]: r[1] for r in locked_seats}
        for seat in seats:
            if seat not in seat_status_map:
                raise ValueError(f"Seat {seat} does not exist for show {show_id}.")
            if seat_status_map[seat] != SeatStatus.AVAILABLE:
                raise ValueError(f"Seat {seat} is not available (status: {seat_status_map[seat]}).")

        # 4. Flip seat statuses to booked
        cur.execute(f"""
            UPDATE seats 
            SET status = %s 
            WHERE show_id = %s AND seat_label IN ({seat_placeholders});
        """, [SeatStatus.BOOKED, show_id] + list(seats))
        
        # 5. Insert booking
        num_tickets = len(seats)
        cur.execute("""
            INSERT INTO bookings (booking_id, user_id, movie_id, theater_id, screen_no, screen_name, show_id, show_date, show_time, format, num_tickets, price_per_ticket, total_price, status, coupon_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (booking_id, user_id, movie_id, theater_id, screen_no, screen_name, show_id, show_date, show_time, format, num_tickets, price, total_price, BookingStatus.CONFIRMED, actual_coupon_code))
        
        # 6. Insert booking seats
        for seat in seats:
            row_prefix = seat[0]
            seat_type = seat_types.get(row_prefix, "standard") if isinstance(seat_types, dict) else "standard"
            cur.execute("""
                INSERT INTO booking_seats (booking_id, seat_label, seat_type)
                VALUES (%s, %s, %s);
            """, (booking_id, seat, seat_type))
            
    # fetch the newly created booking dict and return
    _seats_cache.pop(show_id, None)
    return get_booking_by_id(booking_id)

def cancel_booking(booking_id: str, refund_amount: float, reason: str) -> dict | None:
    """Atomic cancellation of a booking and releasing seats."""
    with get_db_cursor() as cur:
        # 1. Fetch booking under lock
        cur.execute("SELECT show_id, status FROM bookings WHERE booking_id = %s FOR UPDATE;", (booking_id,))
        booking_row = cur.fetchone()
        if not booking_row:
            logger.error(f"Booking {booking_id} not found.")
            return None
            
        show_id, status = booking_row
        if status == BookingStatus.CANCELLED:
            # already cancelled, just return it
            pass
        else:
            # 2. Fetch seats of this booking
            cur.execute("SELECT seat_label FROM booking_seats WHERE booking_id = %s;", (booking_id,))
            seats = [r[0] for r in cur.fetchall()]
            
            # 3. Release seats
            if seats:
                seat_placeholders = ", ".join(["%s"] * len(seats))
                cur.execute(f"""
                    UPDATE seats 
                    SET status = %s 
                    WHERE show_id = %s AND seat_label IN ({seat_placeholders});
                """, [SeatStatus.AVAILABLE, show_id] + list(seats))
                
            # 4. Update booking
            cur.execute("""
                UPDATE bookings 
                SET status = %s, refund_amount = %s, reason = %s, cancelled_at = CURRENT_TIMESTAMP 
                WHERE booking_id = %s;
            """, (BookingStatus.CANCELLED, refund_amount, reason, booking_id))
            
    _seats_cache.pop(show_id, None)
    return get_booking_by_id(booking_id)

def get_booking_by_id(booking_id: str) -> dict | None:
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT booking_id, user_id, movie_id, theater_id, screen_no, screen_name, show_id, show_date, show_time, 
                   format, num_tickets, price_per_ticket, total_price, status, refund_amount, reason, booked_at, cancelled_at, coupon_code 
            FROM bookings 
            WHERE booking_id = %s;
        """, (booking_id,))
        row = cur.fetchone()
        return booking_row_to_dict(row)

def get_user_bookings(user_id: str) -> list[dict]:
    try:
        uuid.UUID(user_id)
    except ValueError:
        from src.db.seed import get_user_uuid
        user_id = get_user_uuid(user_id)
        
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT booking_id, user_id, movie_id, theater_id, screen_no, screen_name, show_id, show_date, show_time, 
                   format, num_tickets, price_per_ticket, total_price, status, refund_amount, reason, booked_at, cancelled_at, coupon_code 
            FROM bookings 
            WHERE user_id = %s 
            ORDER BY booked_at DESC;
        """, (user_id,))
        return [booking_row_to_dict(r) for r in cur.fetchall()]

# --- Policy Services ---

@lru_cache(maxsize=32)
def get_policies_by_topic(topic: str) -> list[dict]:
    with get_db_cursor() as cur:
        cur.execute("SELECT chunk_id, topic, content FROM policies WHERE topic = %s;", (topic,))
        return [{
            "chunk_id": r[0],
            "topic": r[1],
            "text": r[2]
        } for r in cur.fetchall()]

# --- Coupon Services ---

def get_active_coupons() -> list[dict]:
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT coupon_code, discount_type, discount_value, movie_id, theater_id, theater_brand, description, is_active
            FROM coupons
            WHERE is_active = TRUE;
        """)
        rows = cur.fetchall()
        return [{
            "coupon_code": r[0],
            "discount_type": r[1],
            "discount_value": r[2],
            "movie_id": r[3],
            "theater_id": r[4],
            "theater_brand": r[5],
            "description": r[6],
            "is_active": r[7]
        } for r in rows]

def get_coupon_by_code(coupon_code: str) -> dict | None:
    if not coupon_code:
        return None
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT coupon_code, discount_type, discount_value, movie_id, theater_id, theater_brand, description, is_active
            FROM coupons
            WHERE UPPER(coupon_code) = UPPER(%s);
        """, (coupon_code.strip(),))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "coupon_code": row[0],
            "discount_type": row[1],
            "discount_value": row[2],
            "movie_id": row[3],
            "theater_id": row[4],
            "theater_brand": row[5],
            "description": row[6],
            "is_active": row[7]
        }

def has_user_used_coupon(user_id: str, coupon_code: str) -> bool:
    try:
        uuid.UUID(user_id)
    except ValueError:
        from src.db.seed import get_user_uuid
        user_id = get_user_uuid(user_id)
        
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) 
            FROM bookings 
            WHERE user_id = %s AND UPPER(coupon_code) = UPPER(%s) AND status = %s;
        """, (user_id, coupon_code.strip(), BookingStatus.CONFIRMED))
        count = cur.fetchone()[0]
        return count > 0
