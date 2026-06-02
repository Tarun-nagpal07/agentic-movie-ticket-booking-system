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



# from dotenv import load_dotenv
# import os
# from langchain.agents import create_agent
# from langchain.chat_models import init_chat_model
# from src.config.settings import settings
# from src.tools.seat_tools import get_seat_map, get_seats_available, get_seats_types_available
# load_dotenv()

# model = init_chat_model(
#     model=settings.LLM_MODEL,
#     api_key = settings.API_KEY,
#     base_url= settings.BASE_URL
# )


# agent = create_agent(
#     model=model,
#     tools=[get_seats_types_available, get_seat_map,get_seats_available],
#     system_prompt = """
# You are a movie ticket booking assistant.
# now lets 
# city : "ahmedabad"
# date : "2025-06-01"
# theater_id : "t1:
# movie_id:"m1"
# show_id:"s101"
# seat_types:"E"

# Rules:
# 1. Always use tools to answer questions about theaters, movies, and showtimes.
# 2. Use information from the conversation history before asking follow-up questions.
# 3. If the user already mentioned a city earlier in the conversation, do not ask for it again.
# 4. If the user answers a previous question (for example, "Ahmedabad"), treat it as the missing information requested earlier and continue the task.
# 5. When enough information is available, call the appropriate tool immediately.
# 6. Only answer questions related to movie ticket booking.
# 7. For unrelated questions, politely refuse and redirect the conversation toward movie ticket booking.
# """
# )

# result = agent.invoke({"message" : [{"role":"user","content":"my user id is u1,give me seats map?"}]})
# print(result)

# booking

# agent = create_agent(
#     model=model,
#     tools=[get_theater_by_city, get_movies_now_showing, get_showtimes ],
#     system_prompt = """
# You are a movie ticket booking assistant.
# now lets 
# city : "ahmedabad"
# date : "2025-06-01"
# You have access to the following tools:
# - get_theater_by_city
# - get_movies_now_showing
# - get_showtimes

# Rules:
# 1. Always use tools to answer questions about theaters, movies, and showtimes.
# 2. Use information from the conversation history before asking follow-up questions.
# 3. If the user already mentioned a city earlier in the conversation, do not ask for it again.
# 4. If the user answers a previous question (for example, "Ahmedabad"), treat it as the missing information requested earlier and continue the task.
# 5. When enough information is available, call the appropriate tool immediately.
# 6. Only answer questions related to movie ticket booking.
# 7. For unrelated questions, politely refuse and redirect the conversation toward movie ticket booking.
# """
# )



