import uuid
import json
import os
import sys

# Add workspace root to sys.path
sys.path.insert(0, "/Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system")

from src.db.postgres import get_db_cursor, init_db

def deduplicate_messages(serialized_msgs):
    seen_ids = set()
    seen_sigs = set()
    deduped = []
    
    for m in serialized_msgs:
        m_id = m.get("data", {}).get("id")
        content = m.get("data", {}).get("content")
        m_type = m.get("type")
        
        # Check if ID has been seen (and is not None)
        if m_id and m_id in seen_ids:
            print(f"Skipping duplicate message by ID: {m_id}")
            continue
            
        # Check if same content & type has been seen (to catch legacy/None duplicates)
        sig = (m_type, content)
        if sig in seen_sigs:
            print(f"Skipping duplicate message by Content: type={m_type}, content={content[:40]!r}")
            continue
            
        # Ensure it has a valid ID now
        if not m_id:
            new_id = str(uuid.uuid4())
            if "data" not in m:
                m["data"] = {}
            m["data"]["id"] = new_id
            m_id = new_id
            print(f"Assigned new ID {new_id} to message")
            
        deduped.append(m)
        seen_ids.add(m_id)
        seen_sigs.add(sig)
        
    return deduped

def run_migration():
    init_db()
    with get_db_cursor() as cur:
        cur.execute("SELECT user_id, thread_id, messages FROM chat_messages;")
        rows = cur.fetchall()
        print(f"Found {len(rows)} threads to check.")
        
        for user_id, thread_id, messages_json in rows:
            print(f"\nProcessing user={user_id}, thread={thread_id}...")
            if not messages_json:
                continue
                
            # Parse messages if stored as string
            if isinstance(messages_json, str):
                messages_list = json.loads(messages_json)
            else:
                messages_list = messages_json
                
            orig_len = len(messages_list)
            cleaned_list = deduplicate_messages(messages_list)
            new_len = len(cleaned_list)
            print(f"Reduced messages count from {orig_len} to {new_len}")
            
            # Update row in database
            cur.execute(
                """
                UPDATE chat_messages
                SET messages = %s::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND thread_id = %s;
                """,
                (json.dumps(cleaned_list), user_id, thread_id)
            )
            print(f"Successfully updated thread {thread_id}")

if __name__ == "__main__":
    run_migration()
