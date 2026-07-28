import uuid

from app.langraph.nodes import (
    query_rewriter,
    decision_router,
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

    graph.add_node("query_planner", query_rewriter)
    graph.add_node("fetch_data", fetch_data)
    graph.add_node("general_chat", general_chat)
    graph.add_node("rag_response", rag_response)

    graph.add_edge(START, "query_planner")
    graph.add_conditional_edges(
        "query_planner",
        decision_router,
        {"fetch_data": "fetch_data", "general_chat": "general_chat"},
    )
    graph.add_edge("fetch_data", "rag_response")
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
    auth_header = query.auth_header
    source_document_ids = query.source_document_ids or None

    logger.info(
        f"[execute_graph] thread_id={thread_id!r}, model={model_name!r}, "
        f"user_id={user_id!r}, source_document_ids={source_document_ids!r}"
    )

    graph_config = {
        "configurable": {
            "thread_id": thread_id,
            "llm": llm,
            "user_id": user_id,
            "auth_header": auth_header,
            "source_document_ids": source_document_ids,
            "chatbot_config": {
                "bot_name": query.bot_name,
                "bot_description": query.bot_description,
                "fallback_message": query.fallback_message,
                "page_url": query.page_url,
                "visitor_email": query.visitor_email,
                "customer_context": query.customer_context,
            },
        }
    }

    initial_state = {
        "messages": [HumanMessage(content=query.message)],
        # Reset per-turn channels so persisted checkpoints never leak old retrieval/output data.
        "standalone_query": "",
        "relevance": "irrelevant",
        "final_response": "",
        "source_documents": [],
        "retrieved_texts": [],
        "document_ids": [],
        "retrieval_response_time_ms": 0.0,
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
    empty_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    prior_state = await graph.aget_state(graph_config)
    prior_usage = (prior_state.values.get("token_usage") if prior_state.values else None) or empty_usage

    logger.info(f"[execute_graph] Invoking graph with query: {query.message!r}")
    result = await graph.ainvoke(initial_state, config=graph_config)
    logger.info(f"[execute_graph] Graph completed. final_response length: {len(result.get('final_response', ''))} chars")

    cumulative = result.get("token_usage") or empty_usage
    token_usage = {
        "prompt_tokens": cumulative["prompt_tokens"] - prior_usage["prompt_tokens"],
        "completion_tokens": cumulative["completion_tokens"] - prior_usage["completion_tokens"],
        "total_tokens": cumulative["total_tokens"] - prior_usage["total_tokens"],
    }
    logger.info(
        f"[execute_graph] Token usage (this turn) — prompt: {token_usage['prompt_tokens']}, "
        f"completion: {token_usage['completion_tokens']}, total: {token_usage['total_tokens']}"
    )
    return {**result, "thread_id": thread_id, "model": model_name, "token_usage": token_usage}
