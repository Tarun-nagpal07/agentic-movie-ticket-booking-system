import os
import requests
import urllib.parse
import re
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from src.utils.logger import get_logger
from src.config.settings import settings
from src.prompts.poster import EXTRACT_TITLES_PROMPT

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

_POSTER_CACHE = {}

def _fetch_tmdb(title: str, api_key: str) -> dict | None:
    """Fetch movie poster and trailer URL from TMDb API, utilizing an in-memory cache to avoid duplicate API calls."""
    if not title:
        return None
        
    normalized_title = title.strip().lower()
    if normalized_title in _POSTER_CACHE:
        logger.info(f"Movie poster cache HIT for '{title}'")
        return _POSTER_CACHE[normalized_title]
        
    logger.info(f"Movie poster cache MISS for '{title}' — fetching from TMDb")
    try:
        # Step 1: Search for the movie by title
        search_url = "https://api.themoviedb.org/3/search/movie"
        res = requests.get(search_url, params={"api_key": api_key, "query": title}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            results = data.get("results", [])
            if not results:
                logger.warning(f"No TMDb results found for title '{title}'")
                # Cache None to avoid repeatedly searching for invalid/missing titles
                _POSTER_CACHE[normalized_title] = None
                return None
            
            # Take the first matched result
            movie_id = results[0]["id"]
            
            # Step 2: Get movie details and videos (trailers)
            movie_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
            details_res = requests.get(movie_url, params={"api_key": api_key, "append_to_response": "videos"}, timeout=5)
            if details_res.status_code == 200:
                details = details_res.json()
                
                # Construct poster URL
                poster_path = details.get("poster_path")
                poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
                
                # Fetch genres
                genres_list = [g["name"] for g in details.get("genres", [])]
                genre_str = ", ".join(genres_list) if genres_list else ""
                
                # Parse release year
                release_date = details.get("release_date", "")
                year = release_date.split("-")[0] if release_date else ""
                
                # Get IMDb/TMDb rating
                rating = str(round(details.get("vote_average", 0.0), 1))
                
                # Find the trailer URL
                trailer_url = None
                videos = details.get("videos", {}).get("results", [])
                
                # First try to find a YouTube Trailer
                trailer_videos = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer"]
                # Fallback to Teaser or any other clip if no Trailer
                if not trailer_videos:
                    trailer_videos = [v for v in videos if v.get("site") == "YouTube"]
                    
                if trailer_videos:
                    video_key = trailer_videos[0].get("key")
                    if video_key:
                        trailer_url = f"https://www.youtube.com/watch?v={video_key}"
                
                # If no trailer video was found at all, fall back to dynamic search scraping
                if not trailer_url:
                    trailer_url = _fetch_youtube_trailer_scraping(details.get('title', title))
                
                # Return standard dict format
                result = {
                    "title": details.get("title", title),
                    "poster_url": poster_url,
                    "rating": rating,
                    "year": year,
                    "genre": genre_str,
                    "trailer_url": trailer_url
                }
                _POSTER_CACHE[normalized_title] = result
                return result
    except Exception as e:
        logger.warning(f"TMDb fetch failed for '{title}': {e}")
    return None

def _fetch_youtube_trailer_scraping(title: str) -> str:
    """Fetch the actual YouTube video watch link key-free by searching and parsing results page."""
    safe_title = urllib.parse.quote_plus(f"{title} official trailer")
    search_url = f"https://www.youtube.com/results?search_query={safe_title}"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        res = requests.get(search_url, headers=headers, timeout=5)
        if res.status_code == 200:
            match = re.search(r'"videoId":"([^"]+)"', res.text)
            if match:
                return f"https://www.youtube.com/watch?v={match.group(1)}"
    except Exception as e:
        logger.warning(f"YouTube search scrape failed for '{title}': {e}")
    # Return search results page as final fallback
    return search_url

def poster_node(state: dict) -> dict:
    """
    Extract movie titles from latest AI message via LLM structured output,
    fetch TMDb/OMDB posters & trailers for each, store in state["movie_posters"].
    """
    tmdb_key = settings.TMDB_API_KEY
    if not tmdb_key:
        logger.warning("TMDB_API_KEY not set — poster_node skipped")
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
        extraction = llm.invoke(EXTRACT_TITLES_PROMPT.format(text=last_ai.content))
        titles = extraction.titles
    except Exception as e:
        logger.error(f"Poster LLM extraction failed: {e}")
        return {"movie_posters": []}

    if not titles:
        return {"movie_posters": []}

    # Fetch posters and trailers (deduplicated)
    seen, posters = set(), []
    for title in titles:
        if title.lower() in seen:
            continue
        seen.add(title.lower())
        
        res = _fetch_tmdb(title, tmdb_key)
        if res:
            posters.append(res)

    logger.info(f"poster_node: extracted {len(titles)} titles, fetched {len(posters)} posters/trailers")
    
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
