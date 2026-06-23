import psycopg2
import psycopg2.pool
from contextlib import contextmanager
from src.config.settings import settings
from src.utils.logger import get_logger
from src.db.seed import seed_database

logger = get_logger(__name__)

_pool = None

def get_pool():
    """Lazily initialize and return the PostgreSQL connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    
    db_url = settings.SUPABASE_DB_URL
    if not db_url:
        logger.error("SUPABASE_DB_URL is not configured in settings/env.")
        raise ValueError("SUPABASE_DB_URL settings is missing.")
    
    try:
        logger.info("Initializing PostgreSQL connection pool...")
        # Min connections: 1, Max connections: 10
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, db_url)
        return _pool
    except Exception as e:
        logger.critical(f"Failed to create PostgreSQL connection pool: {e}", exc_info=True)
        raise

@contextmanager
def get_db_cursor():
    """Context manager to obtain a cursor and automatically commit/rollback with auto-reconnect."""
    pool = get_pool()
    conn = pool.getconn()
    
    # If connection was closed externally, discard and request a new one
    if conn.closed != 0:
        logger.warning("Retrieved closed connection from pool. Recreating...")
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        conn = pool.getconn()
        
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as conn_err:
        logger.error(f"Database connection error: {conn_err}. Discarding connection from pool.")
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        raise
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        if conn.closed == 0:
            pool.putconn(conn)


def init_db(force: bool = False):
    """Verifies that database schema exists and runs database seeding if requested or empty."""
    db_url = settings.SUPABASE_DB_URL
    if not db_url:
        logger.warning("SUPABASE_DB_URL is not set. Database integration is disabled/non-functional.")
        return

    try:
        with get_db_cursor() as cur:
            if force:
                logger.info("Force flag detected. Dropping existing tables for clean seed...")
                cur.execute("""
                    DROP TABLE IF EXISTS user_sessions CASCADE;
                    DROP TABLE IF EXISTS booking_seats CASCADE;
                    DROP TABLE IF EXISTS bookings CASCADE;
                    DROP TABLE IF EXISTS coupons CASCADE;
                    DROP TABLE IF EXISTS seats CASCADE;
                    DROP TABLE IF EXISTS showtimes CASCADE;
                    DROP TABLE IF EXISTS screens CASCADE;
                    DROP TABLE IF EXISTS theaters CASCADE;
                    DROP TABLE IF EXISTS movies CASCADE;
                    DROP TABLE IF EXISTS users CASCADE;
                    DROP TABLE IF EXISTS policies CASCADE;
                    DROP TABLE IF EXISTS chat_messages CASCADE;
                    DROP TABLE IF EXISTS user_preferences CASCADE;
                """)

            logger.info("Creating normalized tables in PostgreSQL...")
            
            # Create UUID extension in Postgres if not exists (helpful for session UUIDs)
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
            except Exception as ext_err:
                logger.warning(f"Could not create uuid-ossp extension: {ext_err}. Proceeding without it if possible.")

            # Users
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    phone VARCHAR(50),
                    city VARCHAR(100),
                    latitude FLOAT,
                    longitude FLOAT,
                    favorite_genres JSONB DEFAULT '[]'::jsonb,
                    preferred_theaters JSONB DEFAULT '[]'::jsonb,
                    preferred_seat_type VARCHAR(50),
                    preferred_format VARCHAR(50),
                    language_pref VARCHAR(50) DEFAULT 'English',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Movies
            cur.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    movie_id VARCHAR(50) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    genre JSONB NOT NULL,
                    language VARCHAR(100),
                    duration_min INTEGER,
                    rating FLOAT,
                    cast_members JSONB,
                    description TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Theaters
            cur.execute("""
                CREATE TABLE IF NOT EXISTS theaters (
                    theater_id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    city VARCHAR(100) NOT NULL,
                    address VARCHAR(500),
                    latitude FLOAT,
                    longitude FLOAT,
                    amenities JSONB DEFAULT '[]'::jsonb,
                    parking BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Coupons
            cur.execute("""
                CREATE TABLE IF NOT EXISTS coupons (
                    coupon_code VARCHAR(50) PRIMARY KEY,
                    discount_type VARCHAR(20) NOT NULL,
                    discount_value FLOAT NOT NULL,
                    movie_id VARCHAR(50) REFERENCES movies(movie_id) ON DELETE CASCADE,
                    theater_id VARCHAR(50) REFERENCES theaters(theater_id) ON DELETE CASCADE,
                    theater_brand VARCHAR(50),
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Screens
            cur.execute("""
                CREATE TABLE IF NOT EXISTS screens (
                    id SERIAL PRIMARY KEY,
                    theater_id VARCHAR(50) REFERENCES theaters(theater_id) ON DELETE CASCADE,
                    screen_no INTEGER NOT NULL,
                    name VARCHAR(100),
                    format VARCHAR(50),
                    capacity INTEGER,
                    UNIQUE (theater_id, screen_no)
                );
            """)

            # Showtimes
            cur.execute("""
                CREATE TABLE IF NOT EXISTS showtimes (
                    show_id VARCHAR(50) PRIMARY KEY,
                    movie_id VARCHAR(50) REFERENCES movies(movie_id) ON DELETE CASCADE,
                    theater_id VARCHAR(50) REFERENCES theaters(theater_id) ON DELETE CASCADE,
                    screen_no INTEGER,
                    screen_name VARCHAR(100),
                    show_date DATE NOT NULL,
                    show_time TIME NOT NULL,
                    format VARCHAR(50),
                    price INTEGER NOT NULL,
                    seat_types JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Seats
            cur.execute("""
                CREATE TABLE IF NOT EXISTS seats (
                    id SERIAL PRIMARY KEY,
                    show_id VARCHAR(50) REFERENCES showtimes(show_id) ON DELETE CASCADE,
                    seat_label VARCHAR(10) NOT NULL,
                    status VARCHAR(50) DEFAULT 'available',
                    UNIQUE (show_id, seat_label)
                );
            """)

            # Bookings
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    booking_id VARCHAR(50) PRIMARY KEY,
                    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    movie_id VARCHAR(50) REFERENCES movies(movie_id) ON DELETE SET NULL,
                    theater_id VARCHAR(50) REFERENCES theaters(theater_id) ON DELETE SET NULL,
                    screen_no INTEGER,
                    screen_name VARCHAR(100),
                    show_id VARCHAR(50) REFERENCES showtimes(show_id) ON DELETE SET NULL,
                    show_date DATE NOT NULL,
                    show_time TIME NOT NULL,
                    format VARCHAR(50),
                    num_tickets INTEGER NOT NULL,
                    price_per_ticket INTEGER NOT NULL,
                    total_price INTEGER NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    refund_amount FLOAT DEFAULT 0.0,
                    reason VARCHAR(255),
                    booked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    cancelled_at TIMESTAMP WITH TIME ZONE
                );
            """)

            # Alter bookings table to support coupons if table already exists
            cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(50);")

            # Booking Seats
            cur.execute("""
                CREATE TABLE IF NOT EXISTS booking_seats (
                    id SERIAL PRIMARY KEY,
                    booking_id VARCHAR(50) REFERENCES bookings(booking_id) ON DELETE CASCADE,
                    seat_label VARCHAR(10) NOT NULL,
                    seat_type VARCHAR(50) NOT NULL
                );
            """)

            # Sessions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    token VARCHAR(500) UNIQUE NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Policies
            cur.execute("""
                CREATE TABLE IF NOT EXISTS policies (
                    chunk_id VARCHAR(50) PRIMARY KEY,
                    topic VARCHAR(100),
                    content TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Chat Messages (needed for FastAPI agent chat endpoints)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    user_id VARCHAR NOT NULL,
                    thread_id VARCHAR NOT NULL,
                    messages JSONB NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, thread_id)
                );
            """)

        logger.info("Database schemas verified/created successfully.")
        
        # Check if users are empty or if force seeding is active
        should_seed = False
        if force:
            should_seed = True
        else:
            with get_db_cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users;")
                count = cur.fetchone()[0]
                if count == 0:
                    should_seed = True
                    
        if should_seed:
            seed_database()
            
    except Exception as e:
        logger.error(f"Failed to verify/initialize database schemas: {e}", exc_info=True)
