from typing import Annotated
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

class StateType(dict):
    messages: Annotated[list, operator.add]
    val: str
    loop_count: int

def node_a(state: dict) -> dict:
    print("Executing Node A, loop_count:", state.get("loop_count", 0))
    return {"loop_count": state.get("loop_count", 0) + 1}

def node_b(state: dict) -> dict:
    print("Executing Node B")
    res = interrupt({"message": "Please confirm Node B"})
    print("Resumed Node B with:", res)
    if res != "ok" and state.get("loop_count", 0) < 2:
        print("Redirecting/looping back to Node A!")
        return {"val": "redirected"}
    return {"val": "finished"}

def route_b(state: dict) -> str:
    if state.get("val") == "redirected":
        return "node_a"
    return END

builder = StateGraph(StateType)
builder.add_node("node_a", node_a)
builder.add_node("node_b", node_b)
builder.add_edge(START, "node_a")
builder.add_edge("node_a", "node_b")
builder.add_conditional_edges("node_b", route_b, {"node_a": "node_a", END: END})

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "test"}}
print("=== Invoking first time ===")
try:
    res = graph.invoke({"messages": ["msg1"], "val": "init", "loop_count": 0}, config)
    print("Invoke returned:", res)
except Exception as e:
    print("Invoke raised:", e)

snapshot = graph.get_state(config)
print("\n=== Snapshot Tasks before second invoke ===")
print("tasks:", snapshot.tasks)

print("\n=== Invoking second time with Command(resume=...) ===")
from langgraph.types import Command
try:
    # We resume the interrupt with "conversational_query" and update state including messages
    res = graph.invoke(Command(resume="conversational_query", update={"val": "new_query", "messages": ["msg_resume"]}), config)
    print("Second invoke returned:", res)
except Exception as e:
    print("Second invoke raised:", e)

snapshot = graph.get_state(config)
print("\n=== Snapshot Tasks after second invoke ===")
print("tasks:", snapshot.tasks)
if snapshot.tasks:
    for i, t in enumerate(snapshot.tasks):
        print(f"task {i}: interrupts={getattr(t, 'interrupts', None)}")
        if getattr(t, 'interrupts', None):
            for j, intr in enumerate(t.interrupts):
                print(f"  interrupt {j}: value={getattr(intr, 'value', None)}")
