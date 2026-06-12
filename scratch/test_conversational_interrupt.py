import os
import sys
import uuid

# Add workspace root to sys.path
sys.path.insert(0, "/Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system")

from src.graph.graph import get_graph
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from main import get_active_interrupt

def test_booking_confirmation():
    print("\n====================================================")
    print("TEST A: BOOKING CONFIRMATION FLOW")
    print("====================================================")
    thread_id = f"test_confirm_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id, "user_id": "u1"}}
    graph = get_graph()
    
    # 1. Start booking flow (user request)
    print("\n--- Step 1: Request booking ---")
    inputs = {
        "messages": [HumanMessage(content="heyy, book 2 tickets of pathan in 12 pm show")],
        "user_id": "u1",
        "thread_id": thread_id
    }
    res = graph.invoke(inputs, config)
    print("Agent output content:", [m.content for m in res["messages"] if m.type == "ai"][-1])
    
    snapshot = graph.get_state(config)
    print("Snapshot next after Step 1:", snapshot.next)
    
    interrupt_info = get_active_interrupt(snapshot)
    print("Is active interrupt after Step 1:", interrupt_info is not None)
    assert interrupt_info is not None, "Should have paused on confirm_node interrupt"
    
    # 2. User confirms by saying "yess"
    print("\n--- Step 2: Say yess ---")
    inputs = {
        "messages": [HumanMessage(content="yess")],
        "user_id": "u1",
        "thread_id": thread_id
    }
    
    # Resume the interrupt
    print("Resuming interrupt with Command")
    res = graph.invoke(Command(resume="yess", update=inputs), config)
    
    snapshot = graph.get_state(config)
    print("Snapshot next after Step 2:", snapshot.next)
    
    # Verify booking is successful and graph completed
    last_msg = [m.content for m in res["messages"] if m.type == "ai"][-1]
    print("Final Agent Response:", last_msg)
    assert "booking has been confirmed" in last_msg.lower() or "successful" in last_msg.lower(), "Booking should be confirmed"
    assert snapshot.next == (), f"Expected graph to complete, got {snapshot.next}"
    assert res.get("booking_draft") is not None, "Booking draft should still be present in state"
    assert res.get("booking_draft").get("status") == "confirmed", "Booking draft status should be confirmed"
    print("[OK] Booking confirmed successfully!")


def test_booking_interruption():
    print("\n====================================================")
    print("TEST B: BOOKING INTERRUPTION FLOW")
    print("====================================================")
    thread_id = f"test_interrupt_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id, "user_id": "u1"}}
    graph = get_graph()
    
    # 1. Start booking flow (user request)
    print("\n--- Step 1: Request booking ---")
    inputs = {
        "messages": [HumanMessage(content="heyy, book 2 tickets of pathan in 12 pm show")],
        "user_id": "u1",
        "thread_id": thread_id
    }
    res = graph.invoke(inputs, config)
    print("Agent output content:", [m.content for m in res["messages"] if m.type == "ai"][-1])
    
    snapshot = graph.get_state(config)
    interrupt_info = get_active_interrupt(snapshot)
    print("Is active interrupt after Step 1:", interrupt_info is not None)
    assert interrupt_info is not None, "Should have paused on confirm_node interrupt"
    
    # 2. User interrupts with a policy question
    print("\n--- Step 2: Interrupt with policy question ---")
    query_msg = "what is the refund policy?"
    inputs = {
        "messages": [HumanMessage(content=query_msg)],
        "user_id": "u1",
        "thread_id": thread_id
    }
    
    # Resume the interrupt with conversational query
    print("Resuming interrupt with Command")
    res = graph.invoke(Command(resume=query_msg, update=inputs), config)
    
    snapshot = graph.get_state(config)
    print("Snapshot next after Step 2:", snapshot.next)
    
    # Verify we got a policy answer and booking draft was cleared
    last_msg = [m.content for m in res["messages"] if m.type == "ai"][-1]
    print("Final Agent Response:\n", last_msg)
    assert "refund" in last_msg.lower() or "cancellation" in last_msg.lower(), "Should have answered policy query"
    assert snapshot.next == (), f"Expected graph to complete, got {snapshot.next}"
    assert res.get("booking_draft") is None, "Booking draft should be cleared"
    print("[OK] Booking interrupted and redirected to policy successfully!")


if __name__ == "__main__":
    test_booking_confirmation()
    test_booking_interruption()
    print("\n====================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("====================================================")
