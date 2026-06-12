import os
import sys

# Add workspace root to sys.path
sys.path.insert(0, "/Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system")

from src.agents.booking import booking_node
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

def run_tests():
    print("====================================================")
    print("TESTING FOLLOW-UP BOOKING FLOW ('now for 2')")
    print("====================================================")

    # We mock the thread state after the first 10 tickets are confirmed.
    # The history contains the conversation of turn 1, and the current message is "now for 2".
    
    # Check that Cinepolis AlphaOne and Animal are in context.
    # We will build the conversation history exactly like the user's logs.
    messages = [
        HumanMessage(content="hey , which movies are shwoing today"),
        AIMessage(content="Here are the movies showing today in Ahmedabad:\n\nCinepolis AlphaOne\n- Animal\n- Pushpa 2"),
        HumanMessage(content="I wann abook for animal 12 tiketcs"),
        AIMessage(content="The system allows a maximum of 10 tickets per booking transaction. I can book the first 10 tickets for you now, and you can book the remaining 2 tickets in a subsequent transaction.\n\nLet's proceed to book the first 10 tickets for Animal at Cinepolis AlphaOne.\n\nRecommended seats: C1, C2, C3, C4, C5, B1, B2, B3, B4, B5"),
        HumanMessage(content="yes"),
        AIMessage(content="Your booking for Animal has been successfully confirmed!\nMovie: Animal\nTheater: Cinepolis AlphaOne\nSeats: C1-C5, B1-B5\nTotal Paid: ₹2600"),
        HumanMessage(content="now for 2")
    ]

    state = {
        "messages": messages,
        "user_id": "u1",
        "city": "ahmedabad",
        "date": "2025-06-01",
        "movie_title": "Animal",
        "theater_id": "t3",
        "movie_id": "m6",
        "show_id": "s302",
        "theater_name": "Cinepolis AlphaOne",
        "confirmed": True,
        "booking_draft": {
            "booking_id": "b_012",
            "user_id": "u1",
            "movie_id": "m6",
            "movie_title": "Animal",
            "theater_id": "t3",
            "theater_name": "Cinepolis AlphaOne",
            "screen_no": 2,
            "screen_name": "Standard 2",
            "show_id": "s302",
            "show_date": "2025-06-01",
            "show_time": "16:00",
            "format": "standard",
            "seats": ["C1", "C2", "C3", "C4", "C5", "B1", "B2", "B3", "B4", "B5"],
            "num_tickets": 10,
            "price_per_ticket": 260,
            "total_price": 2600,
            "status": "confirmed"
        }
    }

    print("Invoking booking_node...")
    try:
        config = {"configurable": {"user_id": "u1", "thread_id": "test_thread"}}
        res = booking_node(state, config)
        print("\n--- Response Messages ---")
        for msg in res["messages"]:
            print(f"[{msg.type}]: {msg.content}")
            if getattr(msg, "tool_calls", None):
                print(f"  Tool Calls: {msg.tool_calls}")
        print("\n--- Next State Values ---")
        print(f"Theater ID: {res.get('theater_id')}")
        print(f"Movie ID: {res.get('movie_id')}")
        print(f"Show ID: {res.get('show_id')}")
        print(f"Draft: {res.get('booking_draft')}")
        
        # Verify no processing loop occurred and the agent successfully initiated seats recommendation
        assert any(
            msg.type == "ai" and getattr(msg, "tool_calls", None) and any(tc["name"] in ("recommend_seats", "get_available_seats") for tc in msg.tool_calls)
            for msg in res["messages"]
        ), "Error: Agent did not call recommend_seats/get_available_seats!"
        
        print("\n[PASS] Follow-up booking verification test passed successfully!")
    except Exception as e:
        print(f"\n[FAIL] Follow-up booking verification test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_tests()
