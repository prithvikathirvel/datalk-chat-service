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
            return "fetch_data"
    except Exception as e:
        logger.error(f"[decision_router] Error: {e}")
        return "general_chat"
