import os
import sys

sys.path.insert(0, "/Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system")

from src.db.postgres import get_db_cursor

def check_constraints():
    with get_db_cursor() as cur:
        # Check constraints
        cur.execute("""
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'chat_messages'::regclass;
        """)
        rows = cur.fetchall()
        print("Constraints on chat_messages:")
        for r in rows:
            print(f"  {r[0]}: {r[1]}")

if __name__ == "__main__":
    check_constraints()
