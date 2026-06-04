# def booking_agent_node(state: BookingState) -> BookingState:
#     result = booking_agent.invoke(state)  # create_react_agent runs here
    
#     # extract booking_draft from last tool message if present
#     booking_draft = None
#     for msg in reversed(result["messages"]):
#         if hasattr(msg, "content") and isinstance(msg.content, dict):
#             if msg.content.get("status") == "draft":
#                 booking_draft = msg.content.get("booking_draft")
#                 break

#     return {
#         **result,
#         "booking_draft": booking_draft
#     }