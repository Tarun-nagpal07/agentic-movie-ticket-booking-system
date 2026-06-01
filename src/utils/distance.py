import math
from src.config.constants import City


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance in kilometers between two points on the Earth"""
    R = 6371  # earth radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def nearest_theaters(user_lat: float, user_lon: float, theaters: list) -> list:
    """
    theaters: list of theater dicts with latitude and longitude
    returns: same list sorted by distance, closest first
             each theater gets a new 'distance_km' field
    """
    for theater in theaters:
        theater["distance_km"] = round(
            haversine_km(user_lat, user_lon, theater["latitude"], theater["longitude"]), 2
        )
    return sorted(theaters, key=lambda t: t["distance_km"])