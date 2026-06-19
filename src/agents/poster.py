import os
import requests
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from src.utils.logger import get_logger
from src.config.settings import settings

logger = get_logger(__name__)

class MovieTitleList(BaseModel):
    titles: list[str]

def _get_poster_llm():
    """Small, fast, cheap model solely for title extraction. Never streaming."""
    return init_chat_model(
        model=settings.LLM_MODEL,
        api_key=settings.API_KEY,
        base_url=settings.BASE_URL,
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
    api_key = settings.OMDB_API_KEY
    if not api_key:
        logger.warning("OMDB_API_KEY not set — poster_node skipped")
        return {"movie_posters": []}

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
    
    # Update last AI message with the movie posters metadata in-place
    updated_kwargs = dict(last_ai.additional_kwargs or {})
    updated_kwargs["movie_posters"] = posters
    
    updated_ai = AIMessage(
        content=last_ai.content,
        id=getattr(last_ai, "id", None),
        additional_kwargs=updated_kwargs,
        response_metadata=getattr(last_ai, "response_metadata", {}),
        tool_calls=getattr(last_ai, "tool_calls", [])
    )
    
    return {"movie_posters": posters, "messages": [updated_ai]}
