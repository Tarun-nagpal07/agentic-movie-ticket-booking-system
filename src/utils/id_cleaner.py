import re
from datetime import datetime
from src.db.postgres import get_db_cursor
from src.utils.date_utils import get_today

# Centralized ID format configurations.
THEATER_ID_PATTERN = r"t\d+"
MOVIE_ID_PATTERN = r"m\d+"
SHOW_ID_PATTERN = r"s\d+"
BOOKING_ID_PATTERN = r"b_?\d+"

# Combined pattern to match any raw database ID (theater, movie, show, booking)
ANY_ID_PATTERN = rf"(?:{THEATER_ID_PATTERN}|{MOVIE_ID_PATTERN}|{SHOW_ID_PATTERN}|{BOOKING_ID_PATTERN})"

# In-memory static caches for lookups to optimize response time
_movies_cache = None
_theaters_cache = None
_showtimes_cache = None

def _load_movies_to_cache():
    global _movies_cache
    if _movies_cache is not None:
        return _movies_cache
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT movie_id, title FROM movies;")
            rows = cur.fetchall()
            _movies_cache = [{"movie_id": r[0], "title": r[1]} for r in rows]
    except Exception:
        _movies_cache = []
    return _movies_cache

def _load_theaters_to_cache():
    global _theaters_cache
    if _theaters_cache is not None:
        return _theaters_cache
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT theater_id, name, city FROM theaters;")
            rows = cur.fetchall()
            _theaters_cache = [{"theater_id": r[0], "name": r[1], "city": r[2]} for r in rows]
    except Exception:
        _theaters_cache = []
    return _theaters_cache

def _load_showtimes_to_cache():
    global _showtimes_cache
    if _showtimes_cache is not None:
        return _showtimes_cache
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT show_id, movie_id, theater_id, show_date, show_time FROM showtimes;")
            rows = cur.fetchall()
            _showtimes_cache = []
            for r in rows:
                show_date_str = r[3].strftime("%Y-%m-%d") if hasattr(r[3], "strftime") else str(r[3])
                show_time_str = r[4].strftime("%H:%M") if hasattr(r[4], "strftime") else str(r[4])[:5]
                _showtimes_cache.append({
                    "show_id": r[0],
                    "movie_id": r[1],
                    "theater_id": r[2],
                    "date": show_date_str,
                    "time": show_time_str
                })
    except Exception:
        _showtimes_cache = []
    return _showtimes_cache


def remove_raw_ids(text: str) -> str:
    """
    Strips raw database IDs from assistant messages using centralized configurations.
    """
    if not text:
        return text

    # 1. Remove parenthesized ID labels: e.g. "(Theater ID: t4)", "(Movie ID: m1)", "(Show ID: s101)", "(ID: t4)"
    text = re.sub(rf"\s*\(\s*(?:theater|movie|show|booking)?\s*id\s*:\s*{ANY_ID_PATTERN}\s*\)", "", text, flags=re.IGNORECASE)
    
    # 2. Remove parenthesized raw IDs: e.g. "(t4)", "(m1)", "(s101)"
    text = re.sub(rf"\s*\(\s*{ANY_ID_PATTERN}\s*\)", "", text, flags=re.IGNORECASE)
    
    # 3. Remove prefixed IDs but keep the preceding noun (e.g. "Theater ID: t4" -> "Theater", "booking ID: b001" -> "booking")
    text = re.sub(rf"\b(theater|movie|show|booking)\s*id\s*:\s*{ANY_ID_PATTERN}\b", r"\1", text, flags=re.IGNORECASE)
    
    # 4. Remove standalone prefixed IDs: e.g. "ID: t4", "id: s101"
    text = re.sub(rf"\b(id\s*:\s*{ANY_ID_PATTERN})\b", "", text, flags=re.IGNORECASE)
    
    # 5. Clean up any trailing dashes/colons/whitespace left behind
    text = re.sub(r"\s*-\s*$", "", text)  # Trailing dash
    text = re.sub(r"\s*:\s*$", "", text)  # Trailing colon
    text = re.sub(r"[^\S\r\n]{2,}", " ", text)   # Double spaces/tabs, preserving newlines
    
    return text.strip()


def resolve_theater_id(theater_name_or_id: str | None) -> str | None:
    if not theater_name_or_id:
        return theater_name_or_id
    # If it matches the configured theater ID format, return it directly
    if re.match(rf"^{THEATER_ID_PATTERN}$", theater_name_or_id.strip()):
        return theater_name_or_id.strip()
        
    theaters = _load_theaters_to_cache()
    for t in theaters:
        if t["name"].lower() == theater_name_or_id.lower() or theater_name_or_id.lower() in t["name"].lower():
            return t["theater_id"]
    return theater_name_or_id


def resolve_movie_id(movie_name_or_id: str | None) -> str | None:
    if not movie_name_or_id:
        return movie_name_or_id
    # If it matches the configured movie ID format, return it directly
    if re.match(rf"^{MOVIE_ID_PATTERN}$", movie_name_or_id.strip()):
        return movie_name_or_id.strip()
        
    movies = _load_movies_to_cache()
    for m in movies:
        if m["title"].lower() == movie_name_or_id.lower() or movie_name_or_id.lower() in m["title"].lower():
            return m["movie_id"]
    return movie_name_or_id


def get_theater_name_by_id(theater_id: str | None) -> str | None:
    if not theater_id:
        return None
    theaters = _load_theaters_to_cache()
    for t in theaters:
        if t["theater_id"] == theater_id:
            return t["name"]
    return None


def get_movie_title_by_id(movie_id: str | None) -> str | None:
    if not movie_id:
        return None
    movies = _load_movies_to_cache()
    for m in movies:
        if m["movie_id"] == movie_id:
            return m["title"]
    return None


def extract_ids_from_tool_calls(messages: list) -> dict:
    """
    Scans list of messages for tool calls and extracts/resolves theater_id, movie_id,
    show_id, theater_name, and movie_title.
    """
    updates = {}
    for msg in reversed(messages):
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            continue
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args") or {}
            
            # 1. get_movies_by_theaters
            if name in ("get_movies_by_theaters", "get_movies_now_showing"):
                t_ids = args.get("theater_ids")
                if t_ids and isinstance(t_ids, list):
                    if len(t_ids) == 1:
                        tid = resolve_theater_id(t_ids[0])
                        if tid:
                            updates["theater_id"] = tid
                            t_name = get_theater_name_by_id(tid)
                            if t_name:
                                updates["theater_name"] = t_name
                    else:
                        updates["theater_id"] = None
                        updates["theater_name"] = None
            
            # 2. get_showtimes
            elif name == "get_showtimes":
                tid = resolve_theater_id(args.get("theater_id"))
                mid = resolve_movie_id(args.get("movie_id"))
                if tid:
                    updates["theater_id"] = tid
                    t_name = get_theater_name_by_id(tid)
                    if t_name:
                        updates["theater_name"] = t_name
                if mid:
                    updates["movie_id"] = mid
                    m_title = get_movie_title_by_id(mid)
                    if m_title:
                        updates["movie_title"] = m_title
            
            # 3. book_tickets
            elif name == "book_tickets":
                sid = args.get("show_id")
                if sid:
                    updates["show_id"] = sid
                    try:
                        showtimes = _load_showtimes_to_cache()
                        for s in showtimes:
                            if s["show_id"] == sid:
                                tid = s["theater_id"]
                                updates["theater_id"] = tid
                                t_name = get_theater_name_by_id(tid)
                                if t_name:
                                    updates["theater_name"] = t_name
                                updates["movie_id"] = s["movie_id"]
                                m_title = get_movie_title_by_id(s["movie_id"])
                                if m_title:
                                    updates["movie_title"] = m_title
                                break
                    except Exception:
                        pass
                        
            # 4. seat tools
            elif name in ("get_available_seats", "recommend_seats"):
                tid = resolve_theater_id(args.get("theater_id"))
                mid = resolve_movie_id(args.get("movie_id"))
                sid = args.get("show_id")
                if tid:
                    updates["theater_id"] = tid
                    t_name = get_theater_name_by_id(tid)
                    if t_name:
                        updates["theater_name"] = t_name
                if mid:
                    updates["movie_id"] = mid
                    m_title = get_movie_title_by_id(mid)
                    if m_title:
                        updates["movie_title"] = m_title
                if sid:
                    updates["show_id"] = sid

        if updates:
            break
            
    return updates


def extract_entities_from_text(text: str) -> dict:
    """
    Scans the given user message text for known theater names or movie titles
    from the database, and returns resolved IDs/names if found.
    """
    if not text:
        return {}
    updates = {}
    
    # 1. Scan for theater names (exact or substring)
    try:
        theaters = _load_theaters_to_cache()
        for t in theaters:
            name = t["name"]
            if name.lower() in text.lower():
                updates["theater_id"] = t["theater_id"]
                updates["theater_name"] = name
                break
    except Exception:
        pass

    # 2. Scan for movie titles
    try:
        movies = _load_movies_to_cache()
        for m in movies:
            title = m["title"]
            if title.lower() in text.lower():
                updates["movie_id"] = m["movie_id"]
                updates["movie_title"] = title
                break
    except Exception:
        pass
        
    return updates


def resolve_implicit_theater(city: str | None, movie_id: str | None, date: str | None) -> dict:
    """
    If a user mentions a movie and a city, but not a theater, check if the movie
    is showing at exactly one theater in that city on the selected date.
    If so, return that theater's ID and name to pre-populate context.
    """
    if not city or not movie_id:
        return {}
    
    date = date or get_today()
    
    try:
        # 1. Get all theaters in this city
        theaters = _load_theaters_to_cache()
        city_theaters = [t for t in theaters if t["city"].lower() == city.lower()]
        city_tids = {t["theater_id"]: t["name"] for t in city_theaters}
        
        if not city_tids:
            return {}
            
        # 2. Check showtimes to find which of these theaters show the movie on the selected date
        showtimes = _load_showtimes_to_cache()
        matching_tids = []
        
        for tid in city_tids:
            shows_on_date = [s for s in showtimes if s["theater_id"] == tid and s["movie_id"] == movie_id and s["date"] == date]
            if shows_on_date:
                matching_tids.append(tid)
                
        # 3. If exactly one theater is showing this movie, return it
        if len(matching_tids) == 1:
            tid = matching_tids[0]
            return {
                "theater_id": tid,
                "theater_name": city_tids[tid]
            }
    except Exception:
        pass
    return {}


def resolve_implicit_show(theater_id: str | None, movie_id: str | None, date: str | None, user_text: str) -> str | None:
    """
    If movie and theater are known, resolve the show_id.
    - If there is exactly one show, return its show_id.
    - Otherwise, try to parse a time (e.g. 16:00, 4pm, 12:00) from user_text
      and find a matching showtime on that date.
    """
    if not theater_id or not movie_id:
        return None
        
    date = date or get_today()
    
    try:
        showtimes = _load_showtimes_to_cache()
        shows_on_date = [s for s in showtimes if s["theater_id"] == theater_id and s["movie_id"] == movie_id and s["date"] == date]
        
        if not shows_on_date:
            return None
            
        # 1. If exactly one show is playing, auto-resolve it
        if len(shows_on_date) == 1:
            return shows_on_date[0]["show_id"]
            
        # 2. Match time in user text (e.g. "16:00" or "4pm")
        user_text_clean = user_text.lower()
        for s in shows_on_date:
            s_time = s["time"]  # e.g. "16:00"
            if s_time in user_text_clean:
                return s["show_id"]
                
            try:
                t_obj = datetime.strptime(s_time, "%H:%M")
                hr_12 = t_obj.strftime("%I:%M").lstrip("0").lower() # e.g. "04:00" -> "4:00"
                hr_12_short = t_obj.strftime("%l").strip() # e.g. "4"
                
                if hr_12 in user_text_clean:
                    return s["show_id"]
                    
                meridian = "pm" if t_obj.hour >= 12 else "am"
                if f"{hr_12_short}{meridian}" in user_text_clean.replace(" ", ""):
                    return s["show_id"]
            except Exception:
                pass
    except Exception:
        pass
    return None


def validate_and_clear_theater_id(city: str | None, theater_id: str | None) -> tuple[str | None, str | None]:
    """
    Checks if the given theater belongs to the selected city.
    If not, clears theater selection. Otherwise returns theater_id and name.
    """
    if not theater_id:
        return None, None
    try:
        theaters = _load_theaters_to_cache()
        for t in theaters:
            if t["theater_id"] == theater_id:
                if city and t["city"].lower() != city.lower():
                    return None, None
                return theater_id, t["name"]
    except Exception:
        pass
    return theater_id, None


def validate_and_clear_show_id(theater_id: str | None, movie_id: str | None, date: str | None, show_id: str | None) -> str | None:
    """
    Checks if the selected show matches the current theater, movie, and date.
    If there is a mismatch, clears the show selection.
    """
    if not show_id:
        return None
    if not theater_id or not movie_id or not date:
        return None
    try:
        showtimes = _load_showtimes_to_cache()
        show = None
        for s in showtimes:
            if s["show_id"] == show_id:
                show = s
                break
        if show:
            if (movie_id and show["movie_id"] != movie_id) or \
               (theater_id and show["theater_id"] != theater_id) or \
               (date and show["date"] != date):
                return None
            return show_id
    except Exception:
        pass
    return show_id
