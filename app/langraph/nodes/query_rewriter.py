from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.langraph.schema import AgentState
from app.langraph.constants.prompts import QUERY_REWRITER_PROMPT
from app.langraph.utils.helper import get_last_human_message, extract_token_usage
from app.core.logging import logger


def _format_history(messages) -> str:
    """Formats the last 6 messages (excluding the current one) as a readable string."""
    lines = []
    for m in messages[:-1][-6:]:
        if isinstance(m, HumanMessage):
            lines.append(f"User: {m.content}")
        elif isinstance(m, AIMessage):
            lines.append(f"Assistant: {m.content}")
    return "\n".join(lines)


async def query_rewriter(agent_state: AgentState, config: RunnableConfig) -> AgentState:
    logger.info("[query_rewriter] Node entered")
    try:
        messages = agent_state["messages"]
        user_message = get_last_human_message(messages)

        # First turn or single message — no rewriting needed; saves one LLM call
        prior_messages = [m for m in messages if not (isinstance(m, HumanMessage) and m.content == user_message)]
        if not prior_messages:
            logger.info("[query_rewriter] First turn — using raw user message as standalone_query")
            return {"standalone_query": user_message}

        llm_service = config["configurable"]["llm"]
        llm_runnable = llm_service.get_llm(structured=False)

        history = _format_history(messages)
        prompt = QUERY_REWRITER_PROMPT.format(history=history, question=user_message)

        logger.info(f"[query_rewriter] Rewriting follow-up query: {user_message!r}")
        response = await llm_service.ainvoke(llm_runnable, [HumanMessage(content=prompt)])
        standalone_query = response.content.strip()

        logger.info(f"[query_rewriter] Standalone query: {standalone_query!r}")
        return {"standalone_query": standalone_query, "token_usage": extract_token_usage(response)}
    except Exception as e:
        logger.error(f"[query_rewriter] Error: {e} — falling back to raw user message")
        return {"standalone_query": get_last_human_message(agent_state["messages"])}
