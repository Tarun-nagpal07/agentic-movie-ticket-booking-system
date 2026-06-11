import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.tools.booking_tools import _resolve_movie_name_to_id
from src.tools.seat_tools import get_available_seats, recommend_seats

print("=== Running Seat & Booking Merge Verification ===")

# Test 1: Fuzzy movie name matching
print("\n--- Test 1: Fuzzy Movie Matching ---")
test_movies = ["patthan", "intersteler", "pushpa", "Pathaan", "Interstellar"]
for m in test_movies:
    resolved = _resolve_movie_name_to_id(m)
    print(f"Name: {m:15} -> Resolved ID: {resolved}")

# Test 2: get_available_seats with and without seat type filter
print("\n--- Test 2: get_available_seats ---")
try:
    res = get_available_seats.invoke({
        "theater_id": "t1",
        "movie_id": "m1",
        "show_id": "s101"
    })
    print("get_available_seats status:", res.get("status"))
    print("total available:", res.get("total_available"))
    print("rows returned:", len(res.get("rows", [])))
    
    # Check filter
    res_recliner = get_available_seats.invoke({
        "theater_id": "t1",
        "movie_id": "m1",
        "show_id": "s101",
        "seat_type": "recliner"
    })
    print("recliner rows filter count:", len(res_recliner.get("rows", [])))
    for row in res_recliner.get("rows", []):
        print(f"Row {row['row']} type: {row['type']} seats: {row['seats']}")
except Exception as e:
    print("Error in get_available_seats:", e)

# Test 3: recommend_seats (History check)
print("\n--- Test 3: recommend_seats (with User History check) ---")
try:
    # We pass user_id = "u1" who has history of booking "recliner"
    res_pref = recommend_seats.invoke({
        "theater_id": "t1",
        "movie_id": "m1",
        "show_id": "s101",
        "num_seats": 2,
        "user_id": "u1"
    })
    print("u1 recommended seats:", res_pref.get("recommended_seats"))
    print("u1 recommended seat type:", res_pref.get("seat_type"))
    print("u1 recommended based on:", res_pref.get("based_on"))

    # We pass user_id = "u2" who has history of booking premium (premium rows: C, D)
    res_pref2 = recommend_seats.invoke({
        "theater_id": "t5",
        "movie_id": "m8",
        "show_id": "s501",
        "num_seats": 2,
        "user_id": "u2"
    })
    print("u2 recommended seats:", res_pref2.get("recommended_seats"))
    print("u2 recommended seat type:", res_pref2.get("seat_type"))
    print("u2 recommended based on:", res_pref2.get("based_on"))
except Exception as e:
    import traceback
    traceback.print_exc()

# Test 4: recommend_seats with explicit seat type override
print("\n--- Test 4: recommend_seats (with Explicit Override) ---")
try:
    res_override = recommend_seats.invoke({
        "theater_id": "t1",
        "movie_id": "m1",
        "show_id": "s101",
        "num_seats": 2,
        "seat_type": "standard"
    })
    print("explicit standard recommended seats:", res_override.get("recommended_seats"))
    print("explicit standard recommended seat type:", res_override.get("seat_type"))
    print("explicit standard recommended based on:", res_override.get("based_on"))
except Exception as e:
    print("Error in recommend_seats override:", e)
