"""
Migration: Add message_id column and unique deduplication constraint to chat_messages.

This script:
1. Adds a `message_id` VARCHAR column (nullable initially)
2. Backfills message_id from the JSONB `message` column's 'id' field
3. Makes the column NOT NULL
4. Adds a UNIQUE constraint on (user_id, thread_id, message_id)
5. Removes duplicate rows (keeping the earliest by `id`)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.postgres import get_db_cursor
from src.utils.logger import get_logger

logger = get_logger("migration")

def migrate():
    with get_db_cursor() as cur:
        # Step 1: Check if column already exists
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'chat_messages' AND column_name = 'message_id';
        """)
        if cur.fetchone():
            print("Column 'message_id' already exists. Checking constraint...")
        else:
            print("Adding 'message_id' column...")
            cur.execute("ALTER TABLE chat_messages ADD COLUMN message_id VARCHAR;")
        
        # Step 2: Backfill message_id from JSONB
        print("Backfilling message_id from JSONB 'message' column...")
        cur.execute("""
            UPDATE chat_messages
            SET message_id = COALESCE(message->>'id', 'legacy-' || id::text)
            WHERE message_id IS NULL;
        """)
        print(f"Backfilled {cur.rowcount} rows.")
        
        # Step 3: Remove duplicates (keep the row with the smallest `id` for each unique combo)
        print("Removing duplicate rows...")
        cur.execute("""
            DELETE FROM chat_messages
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM chat_messages
                GROUP BY user_id, thread_id, message_id
            );
        """)
        print(f"Removed {cur.rowcount} duplicate rows.")
        
        # Step 4: Make NOT NULL
        print("Setting message_id to NOT NULL...")
        cur.execute("ALTER TABLE chat_messages ALTER COLUMN message_id SET NOT NULL;")
        
        # Step 5: Add unique constraint (idempotent)
        print("Adding unique constraint...")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'chat_messages_user_id_thread_id_message_id_key'
                ) THEN
                    ALTER TABLE chat_messages
                    ADD CONSTRAINT chat_messages_user_id_thread_id_message_id_key
                    UNIQUE (user_id, thread_id, message_id);
                END IF;
            END $$;
        """)
        
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
