import requests
import json
import redis
import psycopg2
from src.config.settings import settings
from src.db.postgres import get_db_cursor

API_BASE_URL = "http://127.0.0.1:8005"
TEST_USER = "utest_del"
TEST_THREAD = "test-delete-thread-999"

def run_test():
    print("--- Thread Deletion Verification Test ---")
    
    # 1. Manually insert a test message into PostgreSQL to simulate active chat history
    from langchain_core.messages import HumanMessage, AIMessage, messages_to_dict
    messages = [
        HumanMessage(content="Hello assistant"),
        AIMessage(content="Hello human, how can I help you book tickets today?")
    ]
    serialized = json.dumps(messages_to_dict(messages))
    
    print("Inserting test chat message into PostgreSQL...")
    with get_db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_messages (user_id, thread_id, messages, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, thread_id) DO UPDATE
            SET messages = EXCLUDED.messages, updated_at = CURRENT_TIMESTAMP;
            """,
            (TEST_USER, TEST_THREAD, serialized)
        )
    print("Inserted successfully.")

    # 2. Write dummy checkpoint keys to Redis to simulate LangGraph's Redis checkpointer state
    print("Writing simulated LangGraph checkpointer keys to Redis...")
    r = redis.Redis.from_url(settings.REDIS_URL)
    r.set(f"checkpoint:{TEST_THREAD}:testkey", "checkpoint_data")
    r.set(f"checkpoint_write:{TEST_THREAD}:testkey", "checkpoint_write_data")
    r.set(f"write_keys_zset:{TEST_THREAD}:testkey", "zset_data")
    
    # Verify they were set
    assert r.exists(f"checkpoint:{TEST_THREAD}:testkey") == 1
    assert r.exists(f"checkpoint_write:{TEST_THREAD}:testkey") == 1
    assert r.exists(f"write_keys_zset:{TEST_THREAD}:testkey") == 1
    print("Redis dummy checkpointer keys set and verified.")

    # 3. Call the GET threads endpoint to verify the test thread is listed
    print("Calling GET /chat/threads to verify presence...")
    res = requests.get(f"{API_BASE_URL}/chat/threads", params={"user_id": TEST_USER})
    if res.status_code != 200:
        print(f"Error calling GET /chat/threads: {res.text}")
        return
    threads = res.json().get("threads", [])
    print(f"User threads list: {threads}")
    assert TEST_THREAD in threads, f"Test thread {TEST_THREAD} not found in user threads!"
    print("GET /chat/threads verified successfully.")

    # 4. Call DELETE endpoint to delete the test thread
    print(f"Calling DELETE /chat/threads for thread {TEST_THREAD}...")
    res = requests.delete(f"{API_BASE_URL}/chat/threads", params={"user_id": TEST_USER, "thread_id": TEST_THREAD})
    if res.status_code != 200:
        print(f"Error calling DELETE /chat/threads: {res.text}")
        return
    print(f"Delete response: {res.json()}")

    # 5. Verify it's deleted from PostgreSQL
    print("Verifying deletion from PostgreSQL...")
    with get_db_cursor() as cur:
        cur.execute("SELECT messages FROM chat_messages WHERE user_id = %s AND thread_id = %s;", (TEST_USER, TEST_THREAD))
        row = cur.fetchone()
        assert row is None, "Chat message record still exists in PostgreSQL!"
    print("PostgreSQL record deletion verified.")

    # 6. Verify keys are deleted from Redis
    print("Verifying deletion from Redis...")
    assert r.exists(f"checkpoint:{TEST_THREAD}:testkey") == 0
    assert r.exists(f"checkpoint_write:{TEST_THREAD}:testkey") == 0
    assert r.exists(f"write_keys_zset:{TEST_THREAD}:testkey") == 0
    print("Redis checkpointer keys cleanup verified.")

    # 7. Call GET /chat/threads again to make sure it's gone
    res = requests.get(f"{API_BASE_URL}/chat/threads", params={"user_id": TEST_USER})
    threads_after = res.json().get("threads", [])
    assert TEST_THREAD not in threads_after, "Deleted thread still returned in GET /chat/threads!"
    print("GET /chat/threads confirms thread is gone.")
    
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_test()
