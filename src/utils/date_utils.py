from datetime import datetime, timedelta

def get_today() -> str:
    """Returns today's date in YYYY-MM-DD format"""
    return datetime.now().strftime("%Y-%m-%d")

def get_now() -> str:
    """Returns current date and time in YYYY-MM-DD HH:MM:SS format"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

def is_show_in_future(show_date: str, show_time: str) -> bool:
    """Checks if the show is scheduled for a future date and time"""
    show_dt = datetime.strptime(f"{show_date} {show_time}", "%Y-%m-%d %H:%M")
    return show_dt > datetime.now()


def hours_until_show(show_date: str, show_time: str) -> float:
    """Returns the number of hours until the show starts"""
    show_dt = datetime.strptime(f"{show_date} {show_time}", "%Y-%m-%d %H:%M")
    delta = show_dt - datetime.now()
    return delta.total_seconds() / 3600


def parse_date(date_str: str) -> datetime:
    """Parses a date string in YYYY-MM-DD format and returns a datetime object"""
    return datetime.strptime(date_str, "%Y-%m-%d")


def format_show_datetime(show_date: str, show_time: str) -> str:
    """Formats show date and time into a more readable format"""
    # "2025-06-01 10:00" → "Sunday, 1 June 2025 at 10:00 AM"
    dt = datetime.strptime(f"{show_date} {show_time}", "%Y-%m-%d %H:%M")
    return dt.strftime("%A, %d %B %Y at %I:%M %p")