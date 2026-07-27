from fastapi import Request
from langgraph.graph.state import CompiledStateGraph
import asyncpg

def get_graph(request: Request) -> CompiledStateGraph:
    state = getattr(request.app.state, "graph", None)
    if state is None:
        raise RuntimeError("Graph not initialized — app may still be starting")
    return state

def get_db(request: Request) -> asyncpg.Connection:
    db = getattr(request.app.state, "database", None)
    if db is None:
        raise RuntimeError("Database not initialized — app may still be starting")
    return db