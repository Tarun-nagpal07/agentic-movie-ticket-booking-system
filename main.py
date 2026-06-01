from fastapi import FastAPI
import json

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Hello, World!"}

@app.get("/movies")
def get_movies():
    with open("data/movies.json", "r") as file:
        movies = json.load(file)
    return movies


from src.tools.booking_tools import get_theater_by_city
print(get_theater_by_city("ahmedabad"))