# src/config/constants.py

from enum import Enum

class Intent(str, Enum):
    SEARCH_MOVIES       = "search_movies"
    GET_SHOWTIMES       = "get_showtimes"
    BOOK_TICKETS        = "book_tickets"
    CANCEL_BOOKING      = "cancel_booking"
    GET_HISTORY         = "get_history"
    RECOMMEND_MOVIES    = "recommend_movies"
    SELECT_SEATS        = "select_seats"
    POLICY_QUERY        = "policy_query"
    VIEW_OFFERS         = "view_offers"
    APPLY_COUPON        = "apply_coupon"
    ASK_CITY            = "ask_city"        # city missing from memory
    UNKNOWN             = "unknown"

class BookingStatus(str, Enum):
    CONFIRMED   = "confirmed"
    CANCELLED   = "cancelled"
    PENDING     = "pending"

class SeatType(str, Enum):
    STANDARD    = "standard"
    PREMIUM     = "premium"
    RECLINER    = "recliner"

class ScreenFormat(str, Enum):
    IMAX        = "IMAX"
    DOLBY       = "Dolby"
    FOUR_DX     = "4DX"
    STANDARD    = "standard"

class SeatStatus(str, Enum):
    AVAILABLE   = "available"
    BOOKED      = "booked"

class City(str, Enum):
    AHMEDABAD   = "ahmedabad"
    MUMBAI      = "mumbai"
    DELHI       = "delhi"
    BANGALORE   = "bangalore"

class RefundPolicy:
    FULL_REFUND_HOURS       = 24      # cancel 24h before → 90% back
    PARTIAL_REFUND_HOURS    = 2       # cancel 2-24h before → 50% back
    FULL_REFUND_PERCENT     = 0.90
    PARTIAL_REFUND_PERCENT  = 0.50
    NO_REFUND_PERCENT       = 0.0

class QdrantCollection:
    POLICY_DOCS     = "policy_docs"

class RedisPrefix:
    USER        = "user:"           # user:{user_id}
    SESSION     = "session:"        # session:{thread_id}

class DBFile:
    MOVIES      = "movies"
    THEATERS    = "theaters"
    SHOWTIMES   = "showtimes"
    BOOKINGS    = "bookings"
    USERS       = "users"
    POLICY_DOCS = "policy_docs"

class Limits:
    MAX_TICKETS_PER_BOOKING = 10
    MAX_RECOMMENDATIONS     = 5
    RAG_TOP_K               = 3
    HISTORY_DEFAULT_LIMIT   = 10
    SESSION_TTL_SECONDS     = 7200   # 2 hours in Redis


