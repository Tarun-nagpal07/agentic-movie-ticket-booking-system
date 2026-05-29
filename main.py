from fastapi import FastAPI
import json

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Hello, World!"}

@app.get("/movies")
def get_movies():
    with open("data/movie.json", "r") as file:
        movies = json.load(file)
    return movies
