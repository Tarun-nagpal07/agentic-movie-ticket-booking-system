import asyncio
import os
import sys
from langchain_core.messages import HumanMessage
from src.graph.graph import get_graph

async def main():
    # Make sure we load the env vars
    from dotenv import load_dotenv
    load_dotenv()

    graph = await get_graph()
    state = {
        "messages": [HumanMessage(content="what is the capital of France?")],
        "user_id": "test-user-refusal",
        "thread_id": "test-thread-refusal"
    }
    config = {"configurable": {"thread_id": "test-thread-refusal"}}
    
    print("=== Streaming events for off-topic query ===")
    async for event in graph.astream_events(state, config, version="v2"):
        kind = event["event"]
        node = event.get("metadata", {}).get("langgraph_node", "")
        tags = event.get("tags", []) or event.get("metadata", {}).get("tags", [])
        
        if kind == "on_chat_model_start":
            print(f"\n[Model Start] node: {node}, tags: {tags}")
        elif kind == "on_chat_model_stream":
            # Check if we stream it
            # Only stream tokens from non-planner nodes, OR if it's the refusal response from the planner
            if node != "planner" or "refusal_response" in tags:
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    print(chunk.content, end="", flush=True)
    print("\n\n=== Streaming finished ===")

if __name__ == "__main__":
    asyncio.run(main())
