import uuid

from app.langraph.nodes import (
    query_rewriter,
    relevance_check,
    decision_router,
    result_router,
    general_chat,
    rag_response,
    fetch_data,
)
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from app.langraph.schema import AgentState
from langgraph.graph.state import CompiledStateGraph
from app.model.chat import ChatRequest
from app.service.llm_service import LLMService
from app.core.config import config
from app.core.logging import logger


async def build_graph(checkpointer) -> CompiledStateGraph:
    logger.info("[build_graph] Building LangGraph state graph")
    graph = StateGraph(state_schema=AgentState)

    graph.add_node("query_rewriter", query_rewriter)
    graph.add_node("relevance_check", relevance_check)
    graph.add_node("fetch_data", fetch_data)
    graph.add_node("general_chat", general_chat)
    graph.add_node("rag_response", rag_response)

    graph.add_edge(START, "query_rewriter")
    graph.add_edge("query_rewriter", "relevance_check")
    graph.add_conditional_edges(
        "relevance_check",
        decision_router,
        {"fetch_data": "fetch_data", "general_chat": "general_chat"},
    )
    graph.add_conditional_edges(
        "fetch_data",
        result_router,
        {"rag_response": "rag_response", "general_chat": "general_chat"},
    )
    graph.add_edge("rag_response", END)
    graph.add_edge("general_chat", END)

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("[build_graph] Graph compiled successfully")
    return compiled


async def execute_graph(query: ChatRequest, graph: CompiledStateGraph):
    thread_id = query.thread_id or str(uuid.uuid4())
    model_name = query.model or config.DEFAULT_LLM_MODEL
    llm = LLMService(model_name=model_name)
    user_id = query.user_id

    logger.info(f"[execute_graph] thread_id={thread_id!r}, model={model_name!r}, user_id={user_id!r}")

    graph_config = {"configurable": {"thread_id": thread_id, "llm": llm, "user_id": user_id}}
    initial_state = {
        "messages": [HumanMessage(content=query.message)],
    }

    logger.info(f"[execute_graph] Invoking graph with query: {query.message!r}")
    result = await graph.ainvoke(initial_state, config=graph_config)
    logger.info(f"[execute_graph] Graph completed. final_response length: {len(result.get('final_response', ''))} chars")
    return {**result, "thread_id": thread_id}