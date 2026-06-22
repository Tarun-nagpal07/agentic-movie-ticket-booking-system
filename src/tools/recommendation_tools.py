from langchain.tools import tool
from src.config.constants import Limits
from src.utils.errors import handle_errors, ToolError
from src.utils.date_utils import get_today
from src.utils.distance import nearest_theaters
from src.utils.logger import get_logger
from src.schemas.show import (
    RecommendMoviesRequest,
    RecommendTheatersRequest
)
from src.api import services

logger = get_logger(__name__)

def make_recommendation_tools(user_id: str, memory: dict):
    """
    Factory that returns recommendation tools bound to a specific user_id and memory dict.
    Call this inside the recommendation_node so each invocation gets the correct user context.
    """

    @tool("get_user_preferences")
    @handle_errors(error_class=ToolError)
    def get_user_preferences() -> dict:
        """
        Get current user preferences and history from state.
        Always call this first before any recommendation tool.
        Returns city, favorite genres, preferred seat type, preferred theaters.
        """
        if not memory:
            raise ToolError(
                message=f"No preferences found for user '{user_id}'. Using defaults.",
                code="NO_PREFERENCES_FOUND",
                recoverable=True
            )

        logger.info(f"preferences fetched for user {user_id}")
        return {
            "status":                "success",
            "user_id":               user_id,
            "city":                  memory.get("city"),
            "favorite_genres":       memory.get("favorite_genres", []),
            "preferred_seat_type":   memory.get("preferred_seat_type"),
            "preferred_theaters":    memory.get("preferred_theaters", []),
            "preferred_format":      memory.get("preferred_format"),
            "language_pref":         memory.get("language_pref")
        }

    @tool("recommend_movies_by_preference", args_schema=RecommendMoviesRequest)
    @handle_errors(error_class=ToolError)
    def recommend_movies_by_preference(
        genres: list[str],
        city: str,
        language: str = None,
        limit: int = Limits.MAX_RECOMMENDATIONS,
    ) -> dict:
        """
        Recommend movies currently showing based on user genre and language preferences.
        Always call get_user_preferences first to get genres and city.
        Only recommends movies that are actually showing today in the user's city.

        Args:
            genres: list of preferred genres e.g. ["sci-fi", "thriller"]
            city: user's city e.g. "ahmedabad"
            language: preferred language e.g. "Hindi" — optional
            limit: max recommendations to return, default 5
        """
        date = get_today()
        city_theaters = services.get_theaters_by_city(city)
        if not city_theaters:
            raise ToolError(
                message=f"No theaters found in '{city}'.",
                code="CITY_NOT_FOUND",
                recoverable=True
            )

        theater_ids = [t["theater_id"] for t in city_theaters]

        # find all movies showing today in this city
        showing_movie_ids = set()
        for tid in theater_ids:
            shows = services.get_showtimes_by_theater_and_date(tid, date)
            for s in shows:
                showing_movie_ids.add(s["movie_id"])

        if not showing_movie_ids:
            raise ToolError(
                message=f"No movies showing today in '{city}'.",
                code="NO_MOVIES_TODAY",
                recoverable=True
            )

        movies = services.get_movies()
        movies_lookup = {m["movie_id"]: m for m in movies}
        scored = []

        for movie_id in showing_movie_ids:
            movie = movies_lookup.get(movie_id)
            if not movie:
                continue

            score = 0.0

            # genre match — each matching genre adds to score
            matched_genres = set(movie["genre"]) & set(genres)
            score += len(matched_genres) * 0.4

            # language match
            if language and movie["language"].lower() == language.lower():
                score += 0.3

            # rating boost — normalize rating to 0-0.3 range
            score += (movie["rating"] / 10) * 0.3

            # only include if at least one genre matches
            if matched_genres:
                scored.append({**movie, "match_score": round(score, 2)})

        if not scored:
            raise ToolError(
                message=f"No movies matching preferences {genres} showing today in '{city}'.",
                code="NO_MATCHING_MOVIES",
                recoverable=True
            )

        # sort by score descending
        recommendations = sorted(scored, key=lambda m: m["match_score"], reverse=True)[:limit]

        logger.info(f"found {len(recommendations)} recommendations for genres {genres} in {city}")
        return {
            "status":          "success",
            "date":            date,
            "city":            city,
            "recommendations": recommendations
        }

    @tool("recommend_theaters_for_movie", args_schema=RecommendTheatersRequest)
    @handle_errors(error_class=ToolError)
    def recommend_theaters_for_movie(
        movie_id: str,
        city: str,
    ) -> dict:
        """
        Recommend best theaters showing a specific movie in the user's city.
        Sorts by distance from user's location and preferred theaters.
        Always call after recommend_movies_by_preference to get movie_id.

        Args:
            movie_id: movie ID from recommend_movies result e.g. "m1"
            city: user's city e.g. "ahmedabad"
        """
        date = get_today()
        user_lat = memory.get("latitude")
        user_lon = memory.get("longitude")
        preferred_theaters = memory.get("preferred_theaters", [])

        city_theaters = services.get_theaters_by_city(city)
        if not city_theaters:
            raise ToolError(
                message=f"No theaters found in '{city}'.",
                code="CITY_NOT_FOUND",
                recoverable=True
            )

        # filter only theaters showing this movie today
        showing_theaters = []
        for theater in city_theaters:
            tid = theater["theater_id"]
            shows = services.get_showtimes(tid, movie_id, date)
            if shows:
                showing_theaters.append(theater)

        if not showing_theaters:
            raise ToolError(
                message=f"Movie '{movie_id}' is not showing in any theater in '{city}' today.",
                code="MOVIE_NOT_SHOWING",
                recoverable=True
            )

        # sort by distance if user location available
        if user_lat and user_lon:
            showing_theaters = nearest_theaters(user_lat, user_lon, showing_theaters)

        # boost preferred theaters to top
        preferred = [t for t in showing_theaters if t["theater_id"] in preferred_theaters]
        others    = [t for t in showing_theaters if t["theater_id"] not in preferred_theaters]
        sorted_theaters = preferred + others

        logger.info(f"found {len(sorted_theaters)} theaters for movie {movie_id} in {city}")
        return {
            "status":   "success",
            "movie_id": movie_id,
            "city":     city,
            "theaters": sorted_theaters
        }

    @tool("recommend_based_on_history")
    @handle_errors(error_class=ToolError)
    def recommend_based_on_history() -> dict:
        """
        Recommend movies based on user's booking history.
        Finds genres and movies the user has watched before and suggests similar ones.
        Use when user asks 'suggest something like before' or 'based on my taste'.
        """
        city = memory.get("city")
        try:
            booking_history = services.get_user_bookings(user_id) or []
        except Exception:
            booking_history = []

        if not booking_history:
            raise ToolError(
                message="No booking history found to base recommendations on.",
                code="NO_HISTORY_FOUND",
                recoverable=True
            )

        date = get_today()
        movies = services.get_movies()
        movies_lookup = {m["movie_id"]: m for m in movies}

        # extract genres from watched movies
        watched_ids = {b["movie_id"] for b in booking_history if b.get("movie_id")}
        watched_genres = set()
        for mid in watched_ids:
            movie = movies_lookup.get(mid)
            if movie:
                watched_genres.update(movie["genre"])

        # find movies showing today in city — exclude already watched
        theaters = services.get_theaters_by_city(city)
        theater_ids = [t["theater_id"] for t in theaters]

        showing_ids = set()
        for tid in theater_ids:
            shows = services.get_showtimes_by_theater_and_date(tid, date)
            for s in shows:
                showing_ids.add(s["movie_id"])

        # score unwatched movies against watched genres
        scored = []
        for movie_id in showing_ids - watched_ids:       # exclude watched
            movie = movies_lookup.get(movie_id)
            if not movie:
                continue

            matched = set(movie["genre"]) & watched_genres
            if matched:
                score = round((len(matched) / len(watched_genres)) * 0.7 +
                              (movie["rating"] / 10) * 0.3, 2)
                scored.append({**movie, "match_score": score})

        if not scored:
            raise ToolError(
                message="No new recommendations found based on your history.",
                code="NO_RECOMMENDATIONS",
                recoverable=True
            )

        recommendations = sorted(scored, key=lambda m: m["match_score"], reverse=True)[:Limits.MAX_RECOMMENDATIONS]

        logger.info(f"history-based recommendations for user {user_id}: {[r['title'] for r in recommendations]}")
        return {
            "status":          "success",
            "based_on_genres": list(watched_genres),
            "recommendations": recommendations
        }

    return [
        get_user_preferences,
        recommend_movies_by_preference,
        recommend_theaters_for_movie,
        recommend_based_on_history,
    ]