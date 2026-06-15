import sys
import os
import queue
import time

# Add workspace root to sys.path
sys.path.insert(0, "/Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system")

from src.db.postgres import get_db_cursor, init_db
from src.api.chat_utils import run_graph_in_thread, load_messages_from_postgress
from langchain_core.messages import HumanMessage

def test_flow():
    init_db()
    
    user_id = "test-user-dup"
    thread_id = "test-thread-dup-123"
    
    # 1. Clear existing messages from DB
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM chat_messages WHERE user_id = %s AND thread_id = %s;", (user_id, thread_id))
    print("Database cleared for test session.")
    
    # 2. First message
    inputs1 = {
        "messages": [HumanMessage(content="hey")],
        "user_id": user_id,
        "thread_id": thread_id
    }
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id
        }
    }
    
    q1 = queue.Queue()
    print("--- Sending Turn 1 ---")
    run_graph_in_thread(inputs1, config, q1)
    
    # Wait for completion
    res1 = None
    while True:
        item = q1.get()
        if item is None:
            break
        if item.get("type") == "complete":
            res1 = item
            
    print("Turn 1 complete status:", res1.get("status") if res1 else "failed")
    
    # Check messages in DB
    msgs = load_messages_from_postgress(user_id, thread_id)
    print(f"Messages in DB after Turn 1: {len(msgs)}")
    for i, m in enumerate(msgs):
        print(f"  [{i}] Type: {type(m).__name__}, ID: {m.id}, Content: {m.content!r}")
        
    # 3. Second message
    inputs2 = {
        "messages": [HumanMessage(content="which movies are showing")],
        "user_id": user_id,
        "thread_id": thread_id
    }
    
    q2 = queue.Queue()
    print("--- Sending Turn 2 ---")
    run_graph_in_thread(inputs2, config, q2)
    
    # Wait for completion
    res2 = None
    while True:
        item = q2.get()
        if item is None:
            break
        if item.get("type") == "complete":
            res2 = item
            
    print("Turn 2 complete status:", res2.get("status") if res2 else "failed")
    
    # Check messages in DB again
    msgs_after = load_messages_from_postgress(user_id, thread_id)
    print(f"Messages in DB after Turn 2: {len(msgs_after)}")
    for i, m in enumerate(msgs_after):
        print(f"  [{i}] Type: {type(m).__name__}, ID: {m.id}, Content: {m.content!r}")
        
    # Check for duplicates (by ID or content similarity in the same turn)
    ids = [getattr(m, "id", None) for m in msgs_after]
    duplicates = [item for item in ids if ids.count(item) > 1 and item is not None]
    if duplicates:
        print("❌ DUPLICATES DETECTED! Duplicated IDs:", set(duplicates))
    else:
        print("✅ NO DUPLICATES DETECTED!")

if __name__ == "__main__":
    test_flow()
