import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

def update_movies():
    print("Updating movies.json...")
    movies_file = DATA_DIR / "movies.json"
    with open(movies_file, "r") as f:
        data = json.load(f)
    
    existing_ids = {m["movie_id"] for m in data["movies"]}
    
    new_movies = [
        {
            "movie_id": "m9",
            "title": "Gladiator II",
            "genre": ["action", "drama", "adventure"],
            "language": "English",
            "duration_min": 148,
            "rating": 7.0,
            "cast": ["Paul Mescal", "Pedro Pascal"],
            "description": "Years after witnessing the death of Maximus, Lucius is forced to enter the Colosseum."
        },
        {
            "movie_id": "m10",
            "title": "Singham Again",
            "genre": ["action", "drama", "thriller"],
            "language": "Hindi",
            "duration_min": 160,
            "rating": 6.5,
            "cast": ["Ajay Devgn", "Kareena Kapoor"],
            "description": "Bajirao Singham returns to fight against a massive criminal ring."
        },
        {
            "movie_id": "m11",
            "title": "Wicked",
            "genre": ["fantasy", "musical", "romance"],
            "language": "English",
            "duration_min": 160,
            "rating": 8.1,
            "cast": ["Cynthia Erivo", "Ariana Grande"],
            "description": "The story of how a green-skinned woman framed by the Wizard of Oz becomes the Wicked Witch."
        },
        {
            "movie_id": "m12",
            "title": "Moana 2",
            "genre": ["animation", "adventure", "comedy"],
            "language": "English",
            "duration_min": 100,
            "rating": 7.2,
            "cast": ["Auli'i Cravalho", "Dwayne Johnson"],
            "description": "Moana receives an unexpected call from her wayfinding ancestors."
        }
    ]
    
    added = 0
    for m in new_movies:
        if m["movie_id"] not in existing_ids:
            data["movies"].append(m)
            added += 1
            
    with open(movies_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Added {added} movies to movies.json.")

def update_theaters():
    print("Updating theaters.json...")
    theaters_file = DATA_DIR / "theaters.json"
    with open(theaters_file, "r") as f:
        data = json.load(f)
        
    city_theaters = data["theaters"]
    
    new_theaters = {
        "ahmedabad": [
            {
                "theater_id": "t11",
                "name": "Carnival Cinema Himalaya Mall",
                "city": "ahmedabad",
                "address": "Himalaya Mall, Drive In Rd, Ahmedabad",
                "latitude": 23.0455,
                "longitude": 72.5302,
                "screens": [
                    {"screen_no": 1, "name": "Dolby Screen", "format": "Dolby", "capacity": 28},
                    {"screen_no": 2, "name": "Standard 1", "format": "standard", "capacity": 28}
                ],
                "amenities": ["dolby_atmos", "food_court"],
                "parking": True
            },
            {
                "theater_id": "t12",
                "name": "Wide Angle Cinema",
                "city": "ahmedabad",
                "address": "Satellite, SG Highway, Ahmedabad",
                "latitude": 23.0234,
                "longitude": 72.5085,
                "screens": [
                    {"screen_no": 1, "name": "Standard 1", "format": "standard", "capacity": 28},
                    {"screen_no": 2, "name": "Standard 2", "format": "standard", "capacity": 28}
                ],
                "amenities": ["standard"],
                "parking": True
            }
        ],
        "mumbai": [
            {
                "theater_id": "t13",
                "name": "PVR Phoenix Palladium",
                "city": "mumbai",
                "address": "Senapati Bapat Marg, Lower Parel, Mumbai",
                "latitude": 18.9942,
                "longitude": 72.8258,
                "screens": [
                    {"screen_no": 1, "name": "IMAX Screen", "format": "IMAX", "capacity": 28},
                    {"screen_no": 2, "name": "Standard 1", "format": "standard", "capacity": 28}
                ],
                "amenities": ["imax", "recliner"],
                "parking": True
            },
            {
                "theater_id": "t14",
                "name": "Inox R-City Mall",
                "city": "mumbai",
                "address": "LBS Marg, Ghatkopar West, Mumbai",
                "latitude": 19.0995,
                "longitude": 72.9164,
                "screens": [
                    {"screen_no": 1, "name": "Dolby Screen", "format": "Dolby", "capacity": 28},
                    {"screen_no": 2, "name": "Standard 1", "format": "standard", "capacity": 28}
                ],
                "amenities": ["dolby_atmos"],
                "parking": True
            }
        ],
        "delhi": [
            {
                "theater_id": "t15",
                "name": "INOX Nehru Place",
                "city": "delhi",
                "address": "Nehru Place, New Delhi",
                "latitude": 28.5492,
                "longitude": 77.2515,
                "screens": [
                    {"screen_no": 1, "name": "Dolby Screen", "format": "Dolby", "capacity": 28},
                    {"screen_no": 2, "name": "Standard 1", "format": "standard", "capacity": 28}
                ],
                "amenities": ["dolby_atmos", "food_court"],
                "parking": True
            },
            {
                "theater_id": "t16",
                "name": "PVR Director's Cut",
                "city": "delhi",
                "address": "Ambience Mall, Vasant Kunj, New Delhi",
                "latitude": 28.5412,
                "longitude": 77.1542,
                "screens": [
                    {"screen_no": 1, "name": "Standard 1", "format": "standard", "capacity": 28},
                    {"screen_no": 2, "name": "Standard 2", "format": "standard", "capacity": 28}
                ],
                "amenities": ["standard", "recliner"],
                "parking": True
            }
        ],
        "bangalore": [
            {
                "theater_id": "t17",
                "name": "Cinepolis Nexus Shantiniketan",
                "city": "bangalore",
                "address": "Whitefield, Bangalore",
                "latitude": 12.9845,
                "longitude": 77.7285,
                "screens": [
                    {"screen_no": 1, "name": "Dolby Screen", "format": "Dolby", "capacity": 28},
                    {"screen_no": 2, "name": "Standard 1", "format": "standard", "capacity": 28}
                ],
                "amenities": ["dolby_atmos"],
                "parking": True
            },
            {
                "theater_id": "t18",
                "name": "Inox Mantri Square",
                "city": "bangalore",
                "address": "Sampige Road, Malleshwaram, Bangalore",
                "latitude": 12.9915,
                "longitude": 77.5712,
                "screens": [
                    {"screen_no": 1, "name": "Standard 1", "format": "standard", "capacity": 28},
                    {"screen_no": 2, "name": "Standard 2", "format": "standard", "capacity": 28}
                ],
                "amenities": ["standard", "food_court"],
                "parking": True
            }
        ]
    }
    
    added = 0
    for city, theaters in new_theaters.items():
        existing_tids = {t["theater_id"] for t in city_theaters.get(city, [])}
        for t in theaters:
            if t["theater_id"] not in existing_tids:
                city_theaters.setdefault(city, []).append(t)
                added += 1
                
    with open(theaters_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Added {added} theaters to theaters.json.")

def update_showtimes():
    print("Updating showtimes.json...")
    showtimes_file = DATA_DIR / "showtimes.json"
    with open(showtimes_file, "r") as f:
        data = json.load(f)
        
    showtimes_dict = data["showtimes"]
    
    # Load theaters to get screen capacity dynamically
    with open(DATA_DIR / "theaters.json", "r") as tf:
        theaters_data = json.load(tf)
    
    def get_screen_capacity(theater_id, screen_no):
        for city, t_list in theaters_data.get("theaters", {}).items():
            for t in t_list:
                if t["theater_id"] == theater_id:
                    for s in t.get("screens", []):
                        if s["screen_no"] == screen_no:
                            return s.get("capacity", 28)
        return 28

    def generate_seats_and_types(capacity):
        if capacity == 28:
            seats = {
                "A1": "available", "A2": "available", "A3": "available", "A4": "available", "A5": "available",
                "B1": "available", "B2": "available", "B3": "available", "B4": "available", "B5": "available",
                "C1": "available", "C2": "available", "C3": "available", "C4": "available", "C5": "available",
                "D1": "available", "D2": "available", "D3": "available", "D4": "available", "D5": "available",
                "E1": "available", "E2": "available", "E3": "available", "E4": "available",
                "E5": "available", "E6": "available", "E7": "available", "E8": "available"
            }
            seat_types = {
                "A": "standard",
                "B": "standard",
                "C": "standard",
                "D": "premium",
                "E": "recliner"
            }
        else:  # capacity 20 or fallback
            seats = {
                "A1": "available", "A2": "available", "A3": "available", "A4": "available", "A5": "available",
                "B1": "available", "B2": "available", "B3": "available", "B4": "available", "B5": "available",
                "C1": "available", "C2": "available", "C3": "available", "C4": "available", "C5": "available",
                "D1": "available", "D2": "available", "D3": "available", "D4": "available", "D5": "available"
            }
            seat_types = {
                "A": "standard",
                "B": "standard",
                "C": "standard",
                "D": "premium"
            }
        return seats, seat_types

    # We will generate shows for the requested dates: 2025-06-01, 2025-06-02, 2025-06-03, 2025-06-04
    dates = ["2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04"]
    
    # Define mapping of screens and names for new theaters
    new_theaters_info = {
        "t11": [{"no": 1, "name": "Dolby Screen", "format": "Dolby"}, {"no": 2, "name": "Standard 1", "format": "standard"}],
        "t12": [{"no": 1, "name": "Standard 1", "format": "standard"}, {"no": 2, "name": "Standard 2", "format": "standard"}],
        "t13": [{"no": 1, "name": "IMAX Screen", "format": "IMAX"}, {"no": 2, "name": "Standard 1", "format": "standard"}],
        "t14": [{"no": 1, "name": "Dolby Screen", "format": "Dolby"}, {"no": 2, "name": "Standard 1", "format": "standard"}],
        "t15": [{"no": 1, "name": "Dolby Screen", "format": "Dolby"}, {"no": 2, "name": "Standard 1", "format": "standard"}],
        "t16": [{"no": 1, "name": "Standard 1", "format": "standard"}, {"no": 2, "name": "Standard 2", "format": "standard"}],
        "t17": [{"no": 1, "name": "Dolby Screen", "format": "Dolby"}, {"no": 2, "name": "Standard 1", "format": "standard"}],
        "t18": [{"no": 1, "name": "Standard 1", "format": "standard"}, {"no": 2, "name": "Standard 2", "format": "standard"}]
    }

    # Generate new showtimes
    added_count = 0
    show_id_seq = 2000 # start high to avoid overlap
    
    # 1. Add showtimes for new theaters showing new movies
    for t_id, screens in new_theaters_info.items():
        theater_shows = showtimes_dict.setdefault(t_id, {})
        for m_id in ["m9", "m10", "m11", "m12"]:
            movie_shows = theater_shows.setdefault(m_id, [])
            
            # Check if shows already exist for this movie in this theater to prevent duplication
            if movie_shows:
                continue
                
            for dt in dates:
                # Add 2 showtimes per date
                showtimes_to_add = [
                    {"time": "12:00", "screen": screens[0], "price": 300},
                    {"time": "18:30", "screen": screens[1], "price": 280}
                ]
                for s_info in showtimes_to_add:
                    show_id_seq += 1
                    cap = get_screen_capacity(t_id, s_info["screen"]["no"])
                    seats, seat_types = generate_seats_and_types(cap)
                    
                    movie_shows.append({
                        "show_id": f"s{show_id_seq}",
                        "movie_id": m_id,
                        "theater_id": t_id,
                        "screen_no": s_info["screen"]["no"],
                        "screen_name": s_info["screen"]["name"],
                        "date": dt,
                        "time": s_info["time"],
                        "format": s_info["screen"]["format"],
                        "price": s_info["price"],
                        "seat_types": seat_types,
                        "seats": seats
                    })
                    added_count += 1

    # 2. Add showtimes for new movies in some existing theaters (t1, t4, t7, t9)
    existing_theaters_to_inject = {
        "t1": [{"no": 3, "name": "Standard 1", "format": "standard"}, {"no": 4, "name": "Standard 2", "format": "standard"}],
        "t4": [{"no": 3, "name": "Recliner Hall", "format": "Dolby"}, {"no": 4, "name": "Standard 1", "format": "standard"}],
        "t7": [{"no": 4, "name": "Recliner Hall", "format": "standard"}, {"no": 5, "name": "Standard 1", "format": "standard"}],
        "t9": [{"no": 5, "name": "Standard 1", "format": "standard"}, {"no": 6, "name": "Standard 2", "format": "standard"}]
    }
    
    for t_id, screens in existing_theaters_to_inject.items():
        theater_shows = showtimes_dict.setdefault(t_id, {})
        for m_id in ["m9", "m10", "m11", "m12"]:
            movie_shows = theater_shows.setdefault(m_id, [])
            if movie_shows:
                continue
                
            for dt in dates:
                showtimes_to_add = [
                    {"time": "11:30", "screen": screens[0], "price": 320},
                    {"time": "19:00", "screen": screens[1], "price": 290}
                ]
                for s_info in showtimes_to_add:
                    show_id_seq += 1
                    cap = get_screen_capacity(t_id, s_info["screen"]["no"])
                    seats, seat_types = generate_seats_and_types(cap)
                    
                    movie_shows.append({
                        "show_id": f"s{show_id_seq}",
                        "movie_id": m_id,
                        "theater_id": t_id,
                        "screen_no": s_info["screen"]["no"],
                        "screen_name": s_info["screen"]["name"],
                        "date": dt,
                        "time": s_info["time"],
                        "format": s_info["screen"]["format"],
                        "price": s_info["price"],
                        "seat_types": seat_types,
                        "seats": seats
                    })
                    added_count += 1
                    
    with open(showtimes_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Added {added_count} showtimes to showtimes.json.")

if __name__ == "__main__":
    update_movies()
    update_theaters()
    update_showtimes()
    print("All JSON seed updates completed successfully!")
