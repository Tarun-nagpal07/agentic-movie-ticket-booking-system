CLASSIFY_CONFIRMATION_PROMPT = """You are an assistant determining the user's intent on a confirmation screen.
The user is presented with a booking confirmation and is asked to Approve or Reject it.
The user's response is: "{user_input}"

Classify their response into exactly one of these categories:
- Approve: if they are agreeing, saying yes, confirming, or telling the assistant to go ahead.
- Reject: if they are saying no, rejecting, canceling, or telling the assistant to stop.
- Query: if they are asking a question, trying to change booking details (like number of tickets, seat type, date, movie, showtime), or speaking about something else.

Respond with ONLY one of the words: "Approve", "Reject", or "Query". Do not include punctuation or other text.
"""
