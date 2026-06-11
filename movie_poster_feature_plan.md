# Implementation Plan — Movie Poster Panel (LangGraph + Multi-Model)

Add a **`poster_node`** to the LangGraph graph that uses a dedicated fast LLM (separate from the main agent model) to extract movie titles from the latest AI response, fetches OMDB posters, and stores them in state so Streamlit can display them as a live visual panel.

---

## Why a Separate Graph Node + Multi-Model?

| Concern | Why this approach is right |
|---|---|
| **Reliability** | A small LLM like `gpt-4o-mini` is better at extracting movie names from free-text than a regex — it handles "the film with Prabhas", "both action movies", partial names, etc. |
| **Separation of concerns** | The main agent model focuses on booking/recommendation. The poster model is a lightweight, independent, cheap call |
| **Proper graph integration** | `poster_node` is a proper LangGraph node, so it gets checkpointed, logged in Langfuse, and participates in the graph lifecycle |
| **State-driven** | Poster data lives in `BookingState.movie_posters` — the SSE `complete` event streams it to the frontend. No frontend scraping of chat text needed |

---

## Architecture Overview

```
START → memory_read → planner → agent_node
                                    │
              ┌─────────────────────┴────────────────────────┐
              │ booking_node → confirm_node                   │
              │ recommendation_node                           │
              │ seat_node                                     │  → poster_node → [original_next]
              │ history_node                                  │
              │ cancellation_node → cancel_confirm_node       │
              └───────────────────────────────────────────────┘
                                    │
                              memory_write → END
```

`poster_node` is a **pass-through enrichment step** inserted before each final destination. It runs a fast LLM extraction + OMDB fetch, stores posters in state, then routes to where the node was originally going.

---

## Routing Strategy

> [!IMPORTANT]
> The routing challenge: `poster_node` needs to know its next destination. Solution: each node sets `poster_next_node: str` in state before going to `poster_node`. `poster_node` reads this field and routes conditionally.

**Routing map after `poster_node`:**
```
"memory_write"   → memory_write
"end"            → END
"confirm_node"   → confirm_node   # for booking
"cancel_confirm" → cancel_confirm_node
```

Since `confirm_node` and `cancel_confirm_node` use `interrupt()` (HITL), they need to run **after** `poster_node` so the poster is shown alongside the HITL confirmation UI. This is exactly right — user sees the movie poster while confirming a booking.

---

## Proposed Changes

### Component 1: State Extension

#### [MODIFY] [state.py](file:///Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system/src/graph/state.py)

Add two fields to `BookingState`:

```python
movie_posters: list | None          # [{title, poster_url, rating, year, genre}]
poster_next_node: str | None        # routing field: where poster_node should send to next
```

---

### Component 2: New `poster_node`

#### [NEW] [poster.py](file:///Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system/src/agents/poster.py)

```python
# src/agents/poster.py
"""
poster_node — LangGraph node for movie poster enrichment.

Uses a dedicated fast LLM (gpt-4o-mini or equivalent) to extract movie titles
from the latest AI message, then fetches OMDB poster metadata for each title.
Results are stored in state["movie_posters"] and streamed to the frontend.
"""
import os, requests
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from src.utils.logger import get_logger

logger = get_logger(__name__)

# --- Structured output schema for title extraction ---
class MovieTitleList(BaseModel):
    titles: list[str]  # exact movie titles detected in the message

def _get_poster_llm():
    """Small, fast, cheap model solely for title extraction. Never streaming."""
    return init_chat_model(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        streaming=False
    ).with_structured_output(MovieTitleList)

def _fetch_omdb(title: str, api_key: str) -> dict | None:
    """Fetch OMDB metadata for a single movie title."""
    try:
        res = requests.get(
            "https://www.omdbapi.com/",
            params={"t": title, "apikey": api_key},
            timeout=5
        )
        data = res.json()
        if data.get("Response") == "True" and data.get("Poster", "N/A") != "N/A":
            return {
                "title":      data["Title"],
                "poster_url": data["Poster"],
                "rating":     data.get("imdbRating", "N/A"),
                "year":       data.get("Year", ""),
                "genre":      data.get("Genre", ""),
            }
    except Exception as e:
        logger.warning(f"OMDB fetch failed for '{title}': {e}")
    return None

def poster_node(state: dict) -> dict:
    """
    Extract movie titles from latest AI message via LLM structured output,
    fetch OMDB posters for each, store in state["movie_posters"].
    """
    api_key = os.getenv("OMDB_API_KEY", "")
    if not api_key:
        logger.warning("OMDB_API_KEY not set — poster_node skipped")
        return {}

    # Get the last AI message content
    messages = state.get("messages", [])
    last_ai = next(
        (m for m in reversed(messages)
         if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip()),
        None
    )
    if not last_ai:
        return {"movie_posters": []}

    # Use fast LLM to extract movie title names from the message
    try:
        llm = _get_poster_llm()
        extraction = llm.invoke(
            f"Extract ALL movie titles explicitly mentioned in the following text. "
            f"Return only real movie names that appear in the text, nothing else.\n\n"
            f"Text: {last_ai.content}"
        )
        titles = extraction.titles
    except Exception as e:
        logger.error(f"Poster LLM extraction failed: {e}")
        return {"movie_posters": []}

    if not titles:
        return {"movie_posters": []}

    # Fetch OMDB posters (deduplicated)
    seen, posters = set(), []
    for title in titles:
        if title.lower() in seen:
            continue
        seen.add(title.lower())
        omdb = _fetch_omdb(title, api_key)
        if omdb:
            posters.append(omdb)

    logger.info(f"poster_node: extracted {len(titles)} titles, fetched {len(posters)} posters")
    return {"movie_posters": posters}
```

---

### Component 3: Graph Routing Changes

#### [MODIFY] [graph.py](file:///Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system/src/graph/graph.py)

**Add `poster_node` and update routing:**

```python
from src.agents.poster import poster_node

# New routing function
def route_after_poster(state: dict) -> str:
    return state.get("poster_next_node", "end")

# In get_graph():
builder.add_node("poster_node", poster_node)

# Replace existing edges with poster_node intermediate step:

# booking_node → poster_node → confirm_node
# (booking agent sets poster_next_node="confirm_node")
builder.add_edge("booking_node", "poster_node")

# recommendation_node → poster_node → memory_write
# (recommendation agent sets poster_next_node="memory_write")
builder.add_edge("recommendation_node", "poster_node")

# seat_node → poster_node → END
builder.add_edge("seat_node", "poster_node")

# history_node → poster_node → END
builder.add_edge("history_node", "poster_node")

# cancellation_node → cancel_confirm_node (no poster — no movie discussed)
# keep as-is

# poster_node → conditional routing based on poster_next_node
builder.add_conditional_edges(
    "poster_node",
    route_after_poster,
    {
        "confirm_node":    "confirm_node",
        "cancel_confirm":  "cancel_confirm_node",
        "memory_write":    "memory_write",
        "end":             END,
    }
)
```

**Each agent node sets `poster_next_node` before returning:**

```python
# booking_node → sets: {"poster_next_node": "confirm_node", ...}
# recommendation_node → sets: {"poster_next_node": "memory_write", ...}
# seat_node → sets: {"poster_next_node": "end", ...}
# history_node → sets: {"poster_next_node": "end", ...}
```

---

### Component 4: Backend — Stream Posters in `complete` Event

#### [MODIFY] [main.py](file:///Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system/main.py)

In `run_graph_in_thread` (and both non-streaming endpoints), include `movie_posters` from the snapshot:

```python
all_messages = snapshot.values.get("messages", [])
movie_posters = snapshot.values.get("movie_posters") or []

complete_event = {
    "type":          "complete",
    "status":        status,
    "messages":      formatted_msgs,
    "movie_posters": movie_posters   # ← new field
}
```

---

### Component 5: Settings

#### [MODIFY] [settings.py](file:///Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system/src/config/settings.py)
Add: `OMDB_API_KEY: str = Field(default="")`

#### [MODIFY] [.env](file:///Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system/.env)
Add: `OMDB_API_KEY=7b303f3e`

---

### Component 6: Streamlit — Render Poster Panel

#### [MODIFY] [app.py](file:///Users/tarunnagpal/Documents/agentic-movie-ticket-booking-system/app.py)

**Session state:** `st.session_state.movie_posters = []`

**On `complete` event:**
```python
elif event_type == "complete":
    complete_payload = data
    # Grab posters from this turn
    st.session_state.movie_posters = data.get("movie_posters", [])
```

**Render panel** (above chat container, hidden if empty):
```python
if st.session_state.get("movie_posters"):
    # Horizontal scrollable glassmorphic poster cards
    cards_html = '<div class="glass-header">🎬 In This Conversation</div>'
    cards_html += '<div class="movie-poster-panel">'
    for p in st.session_state.movie_posters:
        cards_html += f'''
        <div class="poster-card">
            <img src="{p["poster_url"]}" alt="{p["title"]}">
            <div class="poster-title">{p["title"]}</div>
            <div class="poster-rating">⭐ {p["rating"]}</div>
            <div class="poster-year">{p["year"]}</div>
        </div>'''
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)
```

---

## Full Data Flow

```
User: "What action movies are showing today?"
         ↓
recommendation_node runs → AI says "Pathaan, Animal, and Pushpa 2 are showing..."
recommendation_node sets poster_next_node = "memory_write"
         ↓
poster_node runs:
  LLM extracts: ["Pathaan", "Animal", "Pushpa 2: The Rule"]
  OMDB fetch:   3 posters retrieved
  State:        movie_posters = [{title, poster_url, rating, ...}, ...]
         ↓
memory_write → END
         ↓
main.py complete event: { ..., "movie_posters": [...] }
         ↓
Streamlit: renders 3 poster cards above chat
```

---

## Verification Plan

### Manual Verification
1. Ask "what movies are now showing?" → all matched movie posters appear
2. Ask "tell me about Interstellar" → only Interstellar poster appears
3. Check Langfuse traces — `poster_node` should show as a distinct span with its own LLM call
4. Ask about policy (no movie) → `movie_posters` is `[]`, panel hidden
5. Book a ticket → poster appears alongside the confirmation panel

### Open Questions

> [!IMPORTANT]
> **1. Which paths get `poster_node`?**
> Plan routes: `booking_node`, `recommendation_node`, `seat_node`, `history_node` through `poster_node`.
> Should `cancellation_node` also go through it? (Cancellation messages mention movie names too)

> [!IMPORTANT]
> **2. Should `movie_posters` persist across turns or only show the current turn's posters?**
> Current plan: replaces on every turn. So if the user asks about Pathaan, then asks about policy, panel hides.
> Alternative: accumulate posters across the session.
