import os
import sys

# Add workspace root to sys.path
sys.path.insert(0, "/Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system")

from src.db.postgres import init_db, get_db_cursor
from src.graph.graph import get_graph
from main import load_messages_from_postgress
import json

def inspect():
    init_db()
    user_id = "u1"
    
    # 1. Find the last thread updated
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT thread_id, updated_at FROM chat_messages WHERE user_id = %s ORDER BY updated_at DESC LIMIT 5;",
            (user_id,)
        )
        rows = cur.fetchall()
        if not rows:
            print("No threads found for user u1")
            return
        
        print("Last 5 threads:")
        for r in rows:
            print(f"  Thread: {r[0]}, Updated: {r[1]}")
        
        thread_id = rows[0][0]
        print(f"\nInspecting thread: {thread_id}")

    # 2. Load messages from Postgres
    messages = load_messages_from_postgress(user_id, thread_id)
    print(f"\n=== Postgres Messages ({len(messages)}) ===")
    for i, m in enumerate(messages):
        msg_id = getattr(m, "id", None)
        print(f"[{i}] {type(m).__name__} (ID: {msg_id})")
        print(f"    Content: {m.content!r}")
        if getattr(m, "tool_calls", None):
            print(f"    Tool Calls: {m.tool_calls}")

    # 3. Load graph state from Redis
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}
    snapshot = graph.get_state(config)
    print("\n=== Graph State ===")
    print("Snapshot next:", snapshot.next)
    print("Snapshot tasks:", snapshot.tasks)
    print("booking_draft in state:", snapshot.values.get("booking_draft"))
    print("confirmed in state:", snapshot.values.get("confirmed"))

if __name__ == "__main__":
    inspect()
