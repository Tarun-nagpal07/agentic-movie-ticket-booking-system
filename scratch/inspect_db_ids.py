import os
import sys

# Add workspace root to sys.path
sys.path.insert(0, "/Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system")

from src.db.postgres import init_db
from main import load_messages_from_postgress

def test():
    init_db()
    # Let's inspect messages for a specific user and thread
    user_id = "u1"
    thread_id = "Cyber-Show-574" # This was the thread in the logs
    
    messages = load_messages_from_postgress(user_id, thread_id)
    print(f"Total messages loaded: {len(messages)}")
    for i, m in enumerate(messages):
        msg_id = getattr(m, "id", None)
        print(f"[{i}] Type: {type(m).__name__}, ID: {msg_id}, Content: {m.content[:50]!r}")

if __name__ == "__main__":
    test()
