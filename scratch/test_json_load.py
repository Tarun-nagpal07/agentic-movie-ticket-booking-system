import json
from langchain_core.messages import ToolMessage

# Mock tool message content
content1 = "{'status': 'draft', 'booking_draft': {'booking_id': 'b1'}}"
content2 = '{"status": "draft", "booking_draft": {"booking_id": "b1"}}'

def try_parse(content):
    if isinstance(content, str):
        try:
            return json.loads(content)
        except Exception as e:
            return f"Error: {e}"
    return content

print("Try parsing content1 (single quotes):", try_parse(content1))
print("Try parsing content2 (double quotes):", try_parse(content2))
