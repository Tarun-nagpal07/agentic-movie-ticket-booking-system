import json
import uuid
from pathlib import Path
from datetime import datetime
import bcrypt
from src.db.postgres import get_db_cursor
from src.utils.logger import get_logger

logger = get_logger(__name__)
DATA_DIR = Path(__file__).parent.parent.parent / "data"

def get_user_uuid(user_id_str: str) -> str:
    """Map a string user ID to a stable UUID."""
    if user_id_str.startswith("u") and len(user_id_str) > 1:
        try:
            val = int(user_id_str[1:])
            return f"00000000-0000-0000-0000-{val:012d}"
        except ValueError:
            pass
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id_str))

def load_json(filename: str) -> dict:
    filepath = DATA_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def seed_database():
    logger.info("Starting database seeding...")
    
    # 1. Seed Policies
    try:
        policies_data = load_json("policy.json")
        policies = policies_data.get("policies", [])
        with get_db_cursor() as cur:
            cur.execute("TRUNCATE TABLE policies CASCADE;")
            for policy in policies:
                cur.execute("""
                    INSERT INTO policies (chunk_id, topic, content)
                    VALUES (%s, %s, %s);
                """, (policy["chunk_id"], policy["topic"], policy["text"]))
        logger.info(f"Seeded {len(policies)} policies.")
    except Exception as e:
        logger.error(f"Error seeding policies: {e}", exc_info=True)

    # 2. Seed Movies
    try:
        movies_data = load_json("movies.json")
        movies = movies_data.get("movies", [])
        with get_db_cursor() as cur:
            cur.execute("TRUNCATE TABLE movies CASCADE;")
            for movie in movies:
                cur.execute("""
                    INSERT INTO movies (movie_id, title, genre, language, duration_min, rating, cast_members, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    movie["movie_id"],
                    movie["title"],
                    json.dumps(movie["genre"]),
                    movie["language"],
                    movie["duration_min"],
                    movie["rating"],
                    json.dumps(movie.get("cast", [])),
                    movie["description"]
                ))
        logger.info(f"Seeded {len(movies)} movies.")
    except Exception as e:
        logger.error(f"Error seeding movies: {e}", exc_info=True)

    # 3. Seed Theaters & Screens
    try:
        theaters_data = load_json("theaters.json")
        theaters_dict = theaters_data.get("theaters", {})
        
        all_theaters = []
        for city, theaters_list in theaters_dict.items():
            for theater in theaters_list:
                all_theaters.append(theater)
                
        with get_db_cursor() as cur:
            cur.execute("TRUNCATE TABLE theaters CASCADE;")
            cur.execute("TRUNCATE TABLE screens CASCADE;")
            
            for theater in all_theaters:
                cur.execute("""
                    INSERT INTO theaters (theater_id, name, city, address, latitude, longitude, amenities, parking)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    theater["theater_id"],
                    theater["name"],
                    theater["city"],
                    theater["address"],
                    theater["latitude"],
                    theater["longitude"],
                    json.dumps(theater.get("amenities", [])),
                    theater.get("parking", False)
                ))
                
                for screen in theater.get("screens", []):
                    cur.execute("""
                        INSERT INTO screens (theater_id, screen_no, name, format, capacity)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (
                        theater["theater_id"],
                        screen["screen_no"],
                        screen["name"],
                        screen["format"],
                        screen["capacity"]
                    ))
        logger.info(f"Seeded {len(all_theaters)} theaters and their screens.")
    except Exception as e:
        logger.error(f"Error seeding theaters and screens: {e}", exc_info=True)

    # 4. Seed Users
    # Seed all users from users.json, password set to "Test@123"
    try:
        users_data = load_json("users.json")
        users_dict = users_data.get("users", {})
        
        password_hash = bcrypt.hashpw(b"Test@123", bcrypt.gensalt()).decode("utf-8")
        
        with get_db_cursor() as cur:
            cur.execute("TRUNCATE TABLE users CASCADE;")
            
            for user_id_str, user in users_dict.items():
                user_uuid = get_user_uuid(user_id_str)
                cur.execute("""
                    INSERT INTO users (id, name, email, password_hash, phone, city, latitude, longitude, favorite_genres, preferred_theaters, preferred_seat_type, preferred_format, language_pref)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    user_uuid,
                    user["name"],
                    user["email"],
                    password_hash,
                    user.get("phone", ""),
                    user.get("city", "ahmedabad"),
                    user.get("latitude", 0.0),
                    user.get("longitude", 0.0),
                    json.dumps(user.get("favorite_genres", [])),
                    json.dumps(user.get("preferred_theaters", [])),
                    user.get("preferred_seat_type"),
                    user.get("preferred_format"),
                    user.get("language_pref", "English")
                ))
        logger.info(f"Seeded {len(users_dict)} users (password: 'Test@123').")
    except Exception as e:
        logger.error(f"Error seeding users: {e}", exc_info=True)

    # 5. Seed Showtimes & Seats
    try:
        showtimes_data = load_json("showtimes.json")
        showtimes_dict = showtimes_data.get("showtimes", {})
        
        all_shows = []
        for theater_id, movies_shows in showtimes_dict.items():
            for movie_id, shows in movies_shows.items():
                for show in shows:
                    all_shows.append(show)
                    
        with get_db_cursor() as cur:
            cur.execute("TRUNCATE TABLE showtimes CASCADE;")
            cur.execute("TRUNCATE TABLE seats CASCADE;")
            
            for show in all_shows:
                # show_time in JSON can be e.g. "10:00" - make sure it's valid format HH:MM
                show_time_str = show["time"]
                if len(show_time_str.split(":")) == 2:
                    show_time_str += ":00"
                
                cur.execute("""
                    INSERT INTO showtimes (show_id, movie_id, theater_id, screen_no, screen_name, show_date, show_time, format, price, seat_types)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    show["show_id"],
                    show["movie_id"],
                    show["theater_id"],
                    show["screen_no"],
                    show["screen_name"],
                    show["date"],
                    show_time_str,
                    show["format"],
                    show["price"],
                    json.dumps(show.get("seat_types", {}))
                ))
                
                # Bulk insert seats for this showtime
                seats_dict = show.get("seats", {})
                if seats_dict:
                    seat_tuples = [(show["show_id"], seat_label, status) for seat_label, status in seats_dict.items()]
                    from psycopg2.extras import execute_values
                    execute_values(cur, """
                        INSERT INTO seats (show_id, seat_label, status)
                        VALUES %s
                        ON CONFLICT (show_id, seat_label) DO NOTHING;
                    """, seat_tuples)
                    
        logger.info(f"Seeded {len(all_shows)} showtimes and their seats.")
    except Exception as e:
        logger.error(f"Error seeding showtimes and seats: {e}", exc_info=True)

    # 6. Seed Bookings & Booking Seats
    try:
        bookings_data = load_json("bookings.json")
        bookings_dict = bookings_data.get("bookings", {})
        
        with get_db_cursor() as cur:
            cur.execute("TRUNCATE TABLE bookings CASCADE;")
            cur.execute("TRUNCATE TABLE booking_seats CASCADE;")
            
            # Fetch valid IDs to prevent Foreign Key violations on mismatched seed data
            cur.execute("SELECT show_id FROM showtimes;")
            valid_show_ids = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT movie_id FROM movies;")
            valid_movie_ids = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT theater_id FROM theaters;")
            valid_theater_ids = {r[0] for r in cur.fetchall()}
            
            for booking_id, booking in bookings_dict.items():
                user_uuid = get_user_uuid(booking["user_id"])
                
                show_id = booking["show_id"]
                if show_id not in valid_show_ids:
                    logger.warning(f"Booking {booking_id} references missing show_id {show_id}. Setting to NULL.")
                    show_id = None
                    
                movie_id = booking["movie_id"]
                if movie_id not in valid_movie_ids:
                    movie_id = None
                    
                theater_id = booking["theater_id"]
                if theater_id not in valid_theater_ids:
                    theater_id = None
                
                # Check showtime exists, otherwise skip or handle gracefully
                show_time_str = booking["show_time"]
                if len(show_time_str.split(":")) == 2:
                    show_time_str += ":00"
                
                # parsed dates/timestamps
                booked_at = booking.get("booked_at")
                cancelled_at = booking.get("cancelled_at")
                
                cur.execute("""
                    INSERT INTO bookings (booking_id, user_id, movie_id, theater_id, screen_no, screen_name, show_id, show_date, show_time, format, num_tickets, price_per_ticket, total_price, status, refund_amount, booked_at, cancelled_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    booking["booking_id"],
                    user_uuid,
                    movie_id,
                    theater_id,
                    booking["screen_no"],
                    booking["screen_name"],
                    show_id,
                    booking["show_date"],
                    show_time_str,
                    booking["format"],
                    booking["num_tickets"],
                    booking["price_per_ticket"],
                    booking["total_price"],
                    booking["status"],
                    booking.get("refund_amount", 0.0),
                    booked_at,
                    cancelled_at
                ))
                
                # insert booking seats
                seats_list = booking.get("seats", [])
                for seat in seats_list:
                    # resolve seat type
                    row_prefix = seat[0]
                    seat_types_dict = booking.get("seat_types", {})
                    if not seat_types_dict:
                        # fetch from showtime if available or guess based on row
                        # A-C: standard, D: premium, E: recliner (commonly used in our JSON)
                        if row_prefix in ["A", "B", "C"]:
                            seat_type = "standard"
                        elif row_prefix == "D":
                            seat_type = "premium"
                        elif row_prefix == "E":
                            seat_type = "recliner"
                        else:
                            seat_type = booking.get("seat_type", "standard")
                    else:
                        seat_type = seat_types_dict.get(row_prefix, booking.get("seat_type", "standard"))
                        
                    cur.execute("""
                        INSERT INTO booking_seats (booking_id, seat_label, seat_type)
                        VALUES (%s, %s, %s);
                    """, (booking["booking_id"], seat, seat_type))
                    
        logger.info(f"Seeded {len(bookings_dict)} bookings and their seats.")
    except Exception as e:
        logger.error(f"Error seeding bookings: {e}", exc_info=True)

    logger.info("Database seeding completed.")

if __name__ == "__main__":
    seed_database()
