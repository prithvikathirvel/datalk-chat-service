from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage

from app.core.logging import logger
from app.langraph.constants.prompts import QUERY_PLANNER_PROMPT
from app.langraph.schema import AgentState, QueryPlanOutput
from app.langraph.utils.helper import (
    extract_token_usage,
    get_chatbot_prompt_parts,
    get_last_human_message,
)


def _format_history(messages) -> str:
    """Formats recent messages (excluding the current one) as readable history."""
    lines = []
    for m in messages[:-1][-8:]:
        if isinstance(m, HumanMessage):
            lines.append(f"User: {m.content}")
        elif isinstance(m, AIMessage):
            lines.append(f"Assistant: {m.content}")
    return "\n".join(lines) or "No prior conversation."


def _fast_route(question: str, scoped_sources: bool) -> str | None:
    """Cheap first-pass route for obvious turns; None means ask the LLM planner."""
    q = " ".join(question.lower().split())
    q_clean = q.strip(" ?!.:,;")
    if not q_clean:
        return "irrelevant"

    short_general = {
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "yes", "no",
        "who are you", "what is your name", "what's your name", "what can you do",
    }
    if q_clean in short_general or (len(q_clean) <= 24 and q_clean.startswith(("hi ", "hello ", "hey "))):
        return "irrelevant"

    retrieval_terms = (
        "document", "file", "pdf", "uploaded", "knowledge base", "source", "policy",
        "manual", "contract", "invoice", "order", "ticket", "account", "billing",
        "refund", "shipping", "pricing", "subscription", "plan", "feature", "product",
        "company", "your", "you offer", "support", "dashboard", "integration", "api key",
        "summarize", "compare", "extract", "according to", "based on", "in the docs",
        "login", "password", "setup", "configure", "install", "how do i", "how can i",
    )
    if any(term in q for term in retrieval_terms):
        return "relevant"

    general_terms = (
        "joke", "poem", "story", "translate", "grammar", "rewrite", "draft", "brainstorm",
        "calculate", "math", "python", "javascript", "sql", "algorithm", "regex",
    )
    if any(term in q for term in general_terms):
        return "irrelevant"

    return None


async def query_rewriter(agent_state: AgentState, config: RunnableConfig) -> AgentState:
    logger.info("[query_planner] Node entered")
    messages = agent_state["messages"]
    user_message = get_last_human_message(messages)
    configurable = config.get("configurable", {})
    scoped_sources = bool(configurable.get("source_document_ids"))

    try:
        has_history = any(isinstance(m, (HumanMessage, AIMessage)) for m in messages[:-1])
        fast_relevance = _fast_route(user_message, scoped_sources)

        # Obvious first turns and tiny acknowledgements avoid an LLM planner call.
        if fast_relevance and (not has_history or fast_relevance == "irrelevant"):
            logger.info(f"[query_planner] Fast route: {fast_relevance!r}")
            return {"standalone_query": user_message, "relevance": fast_relevance}

        llm_service = configurable["llm"]
        llm_runnable = llm_service.get_llm(
            structured=True, output_schema=QueryPlanOutput, include_raw=True
        )
        parts = get_chatbot_prompt_parts(configurable)
        kb_status = "configured source documents available" if scoped_sources else "user document library may be available"
        prompt = QUERY_PLANNER_PROMPT.format(
            history=_format_history(messages),
            question=user_message,
            bot_context=parts["bot_context"],
            kb_status=kb_status,
        )

        logger.info(f"[query_planner] Planning query: {user_message!r}")
        response = await llm_service.ainvoke(llm_runnable, [HumanMessage(content=prompt)])
        parsed = response.get("parsed") if isinstance(response, dict) else response
        raw = response.get("raw") if isinstance(response, dict) else response
        if not parsed:
            raise ValueError("Planner returned no parsed output")

        standalone_query = (parsed.standalone_query or user_message).strip()
        relevance = parsed.relevance or (fast_relevance or "irrelevant")
        logger.info(f"[query_planner] standalone={standalone_query!r}, relevance={relevance!r}")
        return {
            "standalone_query": standalone_query,
            "relevance": relevance,
            "token_usage": extract_token_usage(raw),
        }
    except Exception as e:
        fallback_relevance = _fast_route(user_message, scoped_sources) or ("relevant" if scoped_sources else "irrelevant")
        logger.error(f"[query_planner] Error: {e} — fallback relevance={fallback_relevance!r}")
        return {"standalone_query": user_message, "relevance": fallback_relevance}
