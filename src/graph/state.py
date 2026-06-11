from typing import TypedDict, Annotated
import operator

class BookingState(TypedDict):
    """
    Top-level graph state. Every node in the parent graph
    reads/writes to this. Subgraph states sync overlapping keys.
    """
    messages: Annotated[list, operator.add]  # LangGraph message list (appends)
    user_id: str
    memory: dict                              # user prefs from Redis


    intent: str                               # classified intent (e.g. "book_tickets")
    next_agent: str | None                    # routing target (e.g. "booking", "recommendation")


    booking_draft: dict | None                # from booking agent → confirm node
    cancel_draft: dict | None                 # from cancellation agent → cancel_confirm node

    city : str | None
    movie_title: str | None
    date : str | None
    theater_id: str | None
    movie_id: str | None
    show_id: str | None
    theater_name: str | None

    confirmed: bool | None                    # True/False after human-in-the-loop

    error_message: str | None

    thread_id: str | None                     # session/thread identifier
    redirect_to_planner: bool | None          # redirect conversational interrupts to planner
    last_booking_id: str | None               # ID of most recently confirmed booking in this session


class BookingAgentState(TypedDict):
    """
    Subgraph state for the booking agent.
    Handles: search theaters → search movies → get showtimes → book tickets.
    """
    messages: Annotated[list, operator.add]
    user_id: str

    city: str | None                          # detected/extracted city
    date: str | None
    theater_id: str | None
    movie_id: str | None
    show_id: str | None
    theater_name: str | None
    movie_title: str | None
    search_results: list | None               # theaters or movies found
    selected_show: dict | None                # chosen showtime details

    booking_draft: dict | None                # draft for confirmation



class RecommendationAgentState(TypedDict):
    """
    Subgraph state for the recommendation agent.
    Handles: get preferences → recommend by genre/history → suggest theaters.
    """
    messages: Annotated[list, operator.add]
    user_id: str
    memory: dict

    recommendations: list | None              # scored movie recommendations
    suggested_theaters: list | None           # theaters for top pick


class SeatAgentState(TypedDict):
    """
    Subgraph state for the seat selection agent.
    Handles: get seat map → filter by type → check availability.
    """
    messages: Annotated[list, operator.add]
    user_id: str

    city: str | None
    date: str | None
    theater_id: str | None
    movie_id: str | None
    show_id: str | None
    theater_name: str | None
    movie_title: str | None

    seat_map: dict | None                     # full seat layout with status
    available_seats: list | None              # filtered available seats



class PolicyAgentState(TypedDict):
    """
    Subgraph state for the policy agent.
    Handles: RAG retrieval over policy.json → answer FAQ questions.
    """
    messages: Annotated[list, operator.add]
    user_id: str

    retrieved_chunks: list | None             # top-K policy chunks from RAG
    policy_answer: str | None                 # formatted answer to user


class CancellationAgentState(TypedDict):
    """
    Subgraph state for the cancellation agent.
    Handles: find booking → calculate refund → prepare cancellation draft.
    """
    messages: Annotated[list, operator.add]
    user_id: str

    cancel_draft: dict | None                 # draft for cancel confirmation
    last_booking_id: str | None               # ID of most recently confirmed booking in this session



class HistoryAgentState(TypedDict):
    """
    Subgraph state for the history agent.
    Handles: get booking history, last booking, filter by status.
    """
    messages: Annotated[list, operator.add]
    user_id: str

class MemoryAgentState(TypedDict):
    """
    Subgraph state for the memory agent.
    Runs after confirmations — updates user prefs in Redis.
    """
    messages: Annotated[list, operator.add]
    user_id: str
    memory: dict

    booking_draft: dict | None
    cancel_draft: dict | None
    confirmed: bool | None
