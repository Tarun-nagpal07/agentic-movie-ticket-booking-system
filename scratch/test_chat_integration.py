import sys
import asyncio
import uuid
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.graph.graph import get_graph
from src.db.postgres import init_db, get_db_cursor
from src.api.chat_utils import get_active_interrupt
from langgraph.types import Command
from langchain_core.messages import HumanMessage

async def main():
    print("=== INITIALIZING DATABASE ===")
    init_db(force=True)
    
    print("=== LOADING GRAPH ===")
    graph = await get_graph()
    
    thread_id = f"test_thread_{uuid.uuid4().hex[:6]}"
    user_id = "00000000-0000-0000-0000-000000000001" # u1
    
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id
        }
    }
    
    print(f"\n--- Turn 1: Asking for offers in Ahmedabad ---")
    inputs = {
        "messages": [HumanMessage(content="Hey! What coupon offers are available in Ahmedabad?")],
        "user_id": user_id,
        "thread_id": thread_id
    }
    
    res = await graph.ainvoke(inputs, config)
    last_msg = res["messages"][-1]
    print(f"Agent Response:\n{last_msg.content}\n")
    assert "FILM100" in last_msg.content or "PVR50" in last_msg.content or "offers" in last_msg.content.lower(), "Offers not listed in response"
    
    print(f"\n--- Turn 2: Book seats at PVR and apply coupon ---")
    inputs = {
        "messages": [HumanMessage(content="Book 2 seats for Pathaan at PVR Acropolis Mall for today at 12:00 PM and apply coupon FILM100")],
        "user_id": user_id,
        "thread_id": thread_id
    }
    
    res = await graph.ainvoke(inputs, config)
    snapshot = await graph.aget_state(config)
    interrupt_info = get_active_interrupt(snapshot)
    
    if not interrupt_info:
        print("❌ FAILED: Graph did not pause for confirmation.")
        for m in res["messages"][-3:]:
            print(f"{m.type}: {getattr(m, 'content', '')}")
        return
        
    draft = interrupt_info["data"]
    print(f"✅ Interrupt caught: {interrupt_info['message']}")
    print(f"Draft Details: Original Price = ₹{draft.get('original_price')}, Discount = ₹{draft.get('discount_amount')}, Coupon = {draft.get('coupon_code')}, Total Price = ₹{draft.get('total_price')}")
    
    assert draft.get("coupon_code") == "FILM100", "Coupon code not in draft"
    assert draft.get("discount_amount") == 100.0, "Discount amount not correct"
    assert draft.get("total_price") == draft.get("original_price") - 100.0, "Discount not subtracted from total price"
    
    print(f"\n--- Turn 3: Approve booking ---")
    res = await graph.ainvoke(Command(resume="Approve"), config)
    last_msg = res["messages"][-1]
    print(f"Agent Response:\n{last_msg.content}\n")
    assert "Successful" in last_msg.content or "confirmed" in last_msg.content.lower(), "Booking was not confirmed successfully"
    
    # Check database to see if coupon code was saved
    with get_db_cursor() as cur:
        cur.execute("SELECT coupon_code, total_price FROM bookings WHERE booking_id = %s;", (draft["booking_id"],))
        row = cur.fetchone()
        print(f"Saved DB Booking: Coupon = {row[0]}, Total Price Paid = ₹{row[1]}")
        assert row[0] == "FILM100", "Coupon code not stored in database bookings table"
        assert row[1] == draft["total_price"], "Discounted price not stored in database bookings table"
        
    print(f"\n--- Turn 4: Try to book again using the same coupon ---")
    inputs = {
        "messages": [HumanMessage(content="Actually, also book 2 more seats for the same show and apply coupon FILM100 again")],
        "user_id": user_id,
        "thread_id": thread_id
    }
    res = await graph.ainvoke(inputs, config)
    last_msg = res["messages"][-1]
    print(f"Agent Response:\n{last_msg.content}\n")
    assert any(term in last_msg.content.lower() for term in ["already used", "invalid", "error", "cannot", "used already", "only once"]), "Should have warned about already used coupon code"
    print("✅ E2E Chat Integration Tests PASSED Successfully!")

if __name__ == "__main__":
    asyncio.run(main())
