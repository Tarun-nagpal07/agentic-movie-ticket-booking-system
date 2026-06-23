import sys
import os
from pathlib import Path
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.db.postgres import get_db_cursor
from src.utils.chat_utils import save_messages_to_postgress, load_messages_from_postgress
from langchain_core.messages import AIMessage
from src.api import services

TEST_USER = "test-user-immutability"
TEST_THREAD = "test-thread-immutability"

def run_test():
    print("=== Running Seat Map Immutability Verification ===")
    
    # 1. Clean up any existing test thread
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM chat_messages WHERE user_id = %s AND thread_id = %s;", (TEST_USER, TEST_THREAD))
    
    # 2. Check the current status of D1/D2 in showtime s101
    show_id = "s101"
    seats_before = services.get_show_seats(show_id)
    d1_status_before = seats_before.get("D1")
    print(f"Current database status for seat D1: {d1_status_before}")
    
    # 3. Create and save a message containing a seat map tag
    message_content = f"Here is the seat map: [SEAT_MAP:{show_id}]"
    msg = AIMessage(content=message_content)
    
    print("Saving message to database...")
    save_messages_to_postgress(TEST_USER, TEST_THREAD, [msg])
    
    # 4. Load messages and verify snapshot
    loaded = load_messages_from_postgress(TEST_USER, TEST_THREAD)
    assert len(loaded) == 1, "Expected exactly 1 message in history"
    loaded_msg = loaded[0]
    
    print("Verifying snapshot exists in additional_kwargs...")
    seat_maps = loaded_msg.additional_kwargs.get("seat_maps")
    assert seat_maps is not None, "seat_maps should not be None"
    assert show_id in seat_maps, f"show_id {show_id} should be in seat_maps"
    
    snapshot_d1_status = seat_maps[show_id]["seats"].get("D1")
    print(f"Snapshot status for seat D1: {snapshot_d1_status}")
    assert snapshot_d1_status == d1_status_before, f"Snapshot D1 status {snapshot_d1_status} should match before status {d1_status_before}"
    
    # 5. Modify seat D1 status in database (flip it to 'booked' or 'available' depending on its state)
    target_status = "booked" if d1_status_before == "available" else "available"
    print(f"Updating database status of seat D1 to: {target_status}")
    with get_db_cursor() as cur:
        cur.execute("UPDATE seats SET status = %s WHERE show_id = %s AND seat_label = 'D1';", (target_status, show_id))
    
    # Clear the service seats cache to ensure get_show_seats retrieves the new value
    services._seats_cache.pop(show_id, None)
    
    # Verify DB has changed
    new_db_seats = services.get_show_seats(show_id)
    assert new_db_seats.get("D1") == target_status, "DB update failed"
    print(f"Updated database status for seat D1: {new_db_seats.get('D1')}")
    
    # 6. Load messages again and assert snapshot has not changed (IMUTABILITY VERIFICATION)
    loaded_after = load_messages_from_postgress(TEST_USER, TEST_THREAD)
    loaded_msg_after = loaded_after[0]
    seat_maps_after = loaded_msg_after.additional_kwargs.get("seat_maps")
    snapshot_d1_after = seat_maps_after[show_id]["seats"].get("D1")
    print(f"Snapshot status for seat D1 after DB update: {snapshot_d1_after}")
    
    assert snapshot_d1_after == d1_status_before, "BUG: Historical message rendering changed when database was updated!"
    print("SUCCESS: Historical message seat snapshot remained immutable despite database updates!")
    
    # 7. Restore D1 status
    with get_db_cursor() as cur:
        cur.execute("UPDATE seats SET status = %s WHERE show_id = %s AND seat_label = 'D1';", (d1_status_before, show_id))
    services._seats_cache.pop(show_id, None)
    
    # Cleanup test message
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM chat_messages WHERE user_id = %s AND thread_id = %s;", (TEST_USER, TEST_THREAD))
        
    print("Verification test completed successfully.")

if __name__ == "__main__":
    run_test()
