from app.langraph.schema import AgentState
from app.core.logging import logger


async def decision_router(agent_state: AgentState):
    logger.info("[decision_router] Node entered")
    try:
        relevance = agent_state.get("relevance", "irrelevant")
        logger.info(f"[decision_router] Relevance value: {relevance!r}")
        if relevance == "relevant":
            logger.info("[decision_router] Routing to fetch_data")
            return "fetch_data"
        else:
            logger.info("[decision_router] Routing to general_chat")
            return "general_chat"
    except Exception as e:
        logger.error(f"[decision_router] Error: {e}")
        return "general_chat"


def result_router(agent_state: AgentState) -> str:
    """Edge function: routes to rag_response if chunks were retrieved, else general_chat."""
    retrieved = agent_state.get("retrieved_texts", [])
    if retrieved:
        logger.info(f"[result_router] {len(retrieved)} chunk(s) found — routing to rag_response")
        return "rag_response"
    logger.info("[result_router] No chunks after retry — routing to general_chat")
    return "general_chat"
