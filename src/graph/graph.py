from langgraph.graph import StateGraph, START, END
from src.graph.state import BookingState
from src.agents.memory import memory_read_node, memory_write_node
from src.agents.planner import planner_node
from src.agents.booking import booking_node
from src.agents.recommendation import recommendation_node
from src.agents.policy import policy_node
from src.agents.cancellation import cancellation_node
from src.agents.history import history_node
from src.graph.nodes.confirm import confirm_node
from src.graph.nodes.cancel_confirm import cancel_confirm_node
from src.graph.router import route_agent
from src.memory.short_term import get_checkpointer

def route_confirm_node(state: dict) -> str:
    if state.get("redirect_to_planner"):
        return "planner"
    return "memory_write"

def get_graph():
    # Initialize StateGraph with our parent state schema
    builder = StateGraph(BookingState)

    # Add all nodes
    builder.add_node("memory_read", memory_read_node)
    builder.add_node("planner", planner_node)
    builder.add_node("booking_node", booking_node)
    builder.add_node("recommendation_node", recommendation_node)
    builder.add_node("policy_node", policy_node)
    builder.add_node("cancellation_node", cancellation_node)
    builder.add_node("history_node", history_node)
    builder.add_node("confirm_node", confirm_node)
    builder.add_node("cancel_confirm_node", cancel_confirm_node)
    builder.add_node("memory_write", memory_write_node)

    # Define flow logic
    # Start always goes to memory_read to fetch preferences
    builder.add_edge(START, "memory_read")
    builder.add_edge("memory_read", "planner")

    # From planner, we route conditionally to one of the agent nodes
    builder.add_conditional_edges(
        "planner",
        route_agent,
        {
            "booking_node": "booking_node",
            "recommendation_node": "recommendation_node",
            "cancellation_node": "cancellation_node",
            "history_node": "history_node",
            "policy_node": "policy_node",
            "unknown": END,
        }
    )

    # Route agent nodes to their next steps
    # Booking agent leads to confirmation (HITL check)
    builder.add_edge("booking_node", "confirm_node")
    # After confirmation step, memory write runs or we route back to planner if interrupted
    builder.add_conditional_edges(
        "confirm_node",
        route_confirm_node,
        {
            "planner": "planner",
            "memory_write": "memory_write"
        }
    )

    # Cancellation agent leads to cancel confirmation (HITL check)
    builder.add_edge("cancellation_node", "cancel_confirm_node")
    # After cancellation confirmation step, memory write runs or we route back to planner if interrupted
    builder.add_conditional_edges(
        "cancel_confirm_node",
        route_confirm_node,
        {
            "planner": "planner",
            "memory_write": "memory_write"
        }
    )

    # Recommendation leads to memory write to record user interests/genres
    builder.add_edge("recommendation_node", "memory_write")

    # Seat, policy, and history agents do not change persistent state/memory directly,
    # so they go straight to END (according to the user-approved plan)
    builder.add_edge("policy_node", END)
    builder.add_edge("history_node", END)

    # After memory write runs, the turn is complete
    builder.add_edge("memory_write", END)

    # Compile the graph using Redis checkpointer for short term memory state persistence
    checkpointer = get_checkpointer()
    graph = builder.compile(checkpointer=checkpointer, debug=True)

    return graph
