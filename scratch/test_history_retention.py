import os
import sys

# Add workspace root to sys.path
sys.path.insert(0, "/Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system")

from src.agents.booking import booking_node
from langchain_core.messages import HumanMessage, AIMessage

def run_tests():
    print("====================================================")
    print("TESTING HISTORY RETENTION WITH LONG CHAT (17 messages)")
    print("====================================================")

    # 17 messages in history (all Human or AI without tool calls)
    messages = [
        HumanMessage(content="hi"),
        AIMessage(content="Hello! How can I help you?"),
        HumanMessage(content="what movies are showing today?"),
        AIMessage(content="We have Animal and Pushpa 2 showing today."),
        HumanMessage(content="where is Cinepolis?"),
        AIMessage(content="Cinepolis is at AlphaOne Mall."),
        HumanMessage(content="is there parking?"),
        AIMessage(content="Yes, parking is available."),
        HumanMessage(content="what are the ticket prices?"),
        AIMessage(content="Ticket prices range from 200 to 400 INR."),
        HumanMessage(content="how can I pay?"),
        AIMessage(content="You can pay using credit card, debit card, or UPI."),
        HumanMessage(content="are there standard seats?"),
        AIMessage(content="Yes, we have standard, premium, and recliner seats."),
        HumanMessage(content="can I cancel my booking?"),
        AIMessage(content="Yes, cancellations are allowed up to 2 hours before the show."),
        HumanMessage(content="I want to book tickets for Animal movie at Cinepolis AlphaOne")
    ]

    state = {
        "messages": messages,
        "user_id": "u1",
        "city": "ahmedabad",
        "date": "2025-06-01"
    }

    print(f"Initial messages count: {len(messages)}")
    print("Invoking booking_node...")
    
    try:
        res = booking_node(state)
        returned_messages = res.get("messages", [])
        
        print("\n--- Newly Returned Messages ---")
        for msg in returned_messages:
            print(f"[{msg.type}]: {msg.content}")
            if getattr(msg, "tool_calls", None):
                print(f"  Tool Calls: {msg.tool_calls}")

        print(f"\nReturned messages count: {len(returned_messages)}")
        
        # We expect that the returned messages contain the newly generated AIMessage.
        # It should NOT be empty!
        assert len(returned_messages) > 0, "Error: No messages returned from booking_node! They got lost in slicing."
        
        # Verify the last message returned is an AIMessage (since the node ended by responding to the user)
        assert returned_messages[-1].type == "ai", "Error: The last returned message is not an AIMessage!"
        
        print("\n[PASS] History retention verification test passed successfully!")
    except Exception as e:
        print(f"\n[FAIL] History retention verification test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_tests()
