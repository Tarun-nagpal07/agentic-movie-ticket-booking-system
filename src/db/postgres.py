import json
import psycopg2
import psycopg2.pool
from contextlib import contextmanager
from src.config.settings import settings
from src.utils.logger import get_logger

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
        logger.info("Initializing Supabase/PostgreSQL connection pool...")
        # Min connections: 1, Max connections: 10
        _pool = psycopg2.pool.SimpleConnectionPool(1, 10, db_url)
        return _pool
    except Exception as e:
        logger.critical(f"Failed to create PostgreSQL connection pool: {e}", exc_info=True)
        raise

@contextmanager
def get_db_cursor():
    """Context manager to obtain a cursor and automatically commit/rollback."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        pool.putconn(conn)

def init_db(force: bool = False):
    """Verifies that database schema exists and runs user preferences seeding if empty."""
    db_url = settings.SUPABASE_DB_URL
    if not db_url:
        logger.warning("SUPABASE_DB_URL is not set. Database integration is disabled/non-functional.")
        return

    try:
        with get_db_cursor() as cur:
            logger.info("Verifying user_preferences and chat_messages tables in PostgreSQL...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id VARCHAR PRIMARY KEY,
                    preferences JSONB NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    user_id VARCHAR NOT NULL,
                    thread_id VARCHAR NOT NULL,
                    messages JSONB NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, thread_id)
                );
            """)
        logger.info("Database schemas verified successfully.")
        seed_database_if_empty(force=force)
    except Exception as e:
        logger.error(f"Failed to verify/initialize database schemas: {e}", exc_info=True)

def seed_database_if_empty(force: bool = False):
    """Seeds default user preferences from users.json into the DB."""
    try:
        with get_db_cursor() as cur:
            if force:
                logger.info("Force flag detected. Clearing existing user_preferences table...")
                cur.execute("TRUNCATE TABLE user_preferences;")

            cur.execute("SELECT COUNT(*) FROM user_preferences;")
            count = cur.fetchone()[0]
            if count > 0:
                logger.info("user_preferences table already contains data. Skipping seeding.")
                return

            logger.info("Seeding user_preferences table from users.json...")
            from src.db.json_store import load_db
            from src.config.constants import DBFile

            users_db = load_db(DBFile.USERS)
            users = users_db.get("users", {})

            seeded = 0
            for user_id, user_data in users.items():
                cur.execute("""
                    INSERT INTO user_preferences (user_id, preferences)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO NOTHING;
                """, (user_id, json.dumps(user_data)))
                seeded += 1
            logger.info(f"Successfully seeded {seeded} users into user_preferences.")
    except Exception as e:
        logger.error(f"Error seeding database from users.json: {e}", exc_info=True)
