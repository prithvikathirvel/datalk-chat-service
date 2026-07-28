import json
import re

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.core.logging import logger
from app.langraph.constants.prompts import QUERY_PLANNER_PROMPT
from app.langraph.schema import AgentState
from app.langraph.utils.helper import (
    extract_token_usage,
    get_chatbot_prompt_parts,
    get_last_human_message,
    message_text,
)


def _format_history(messages) -> str:
    lines = []
    for m in messages[:-1][-8:]:
        if isinstance(m, HumanMessage):
            lines.append(f"User: {message_text(m)}")
        elif isinstance(m, AIMessage):
            lines.append(f"Assistant: {message_text(m)}")
    return "\n".join(lines) or "No prior conversation."


def _fast_route(question: str) -> str | None:
    """Cheap route for obvious turns; None means use the planner."""
    q = " ".join(question.lower().split())
    q_clean = q.strip(" ?!.:,;")
    if not q_clean:
        return "irrelevant"

    if q_clean in {
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "yes", "no",
        "who are you", "what is your name", "what's your name", "what can you do",
    } or (len(q_clean) <= 24 and q_clean.startswith(("hi ", "hello ", "hey "))):
        return "irrelevant"

    retrieval_terms = (
        "document", "file", "pdf", "uploaded", "knowledge base", "source", "policy", "manual",
        "contract", "invoice", "order", "ticket", "account", "billing", "refund", "return",
        "shipping", "delivery", "pricing", "price", "cost", "fee", "subscription", "plan",
        "feature", "product", "company", "you offer", "support", "contact", "address", "location",
        "hours", "phone number", "email address", "dashboard", "login",
        "password", "warranty", "integration", "api key", "report", "summarize", "compare",
        "extract", "according to", "based on", "in the docs", "how do i", "how can i",
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


def _parse_plan(text: str, fallback_query: str, fallback_relevance: str) -> tuple[str, str]:
    """Tolerates JSON, fenced JSON, or plain text from different models."""
    cleaned = re.sub(r"```(?:json)?|```", "", text or "").strip()
    data = {}
    match = re.search(r"\{.*\}", cleaned, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
        except Exception:
            data = {}

    standalone = str(data.get("standalone_query") or data.get("query") or "").strip() or fallback_query
    raw_rel = str(data.get("relevance") or data.get("route") or cleaned).lower()
    if "irrelevant" in raw_rel or "general" in raw_rel or "not relevant" in raw_rel or "no retrieval" in raw_rel:
        relevance = "irrelevant"
    elif "relevant" in raw_rel or "rag" in raw_rel or "retrieve" in raw_rel:
        relevance = "relevant"
    else:
        relevance = fallback_relevance
    return standalone, relevance


async def query_rewriter(agent_state: AgentState, config: RunnableConfig) -> AgentState:
    logger.info("[query_planner] Node entered")
    messages = agent_state["messages"]
    user_message = get_last_human_message(messages)
    configurable = config.get("configurable", {})
    has_history = any(isinstance(m, (HumanMessage, AIMessage)) for m in messages[:-1])
    fast_relevance = _fast_route(user_message)

    try:
        if fast_relevance == "irrelevant" or (fast_relevance == "relevant" and not has_history):
            logger.info(f"[query_planner] Fast route: {fast_relevance!r}")
            return {"standalone_query": user_message, "relevance": fast_relevance}

        llm_service = configurable["llm"]
        parts = get_chatbot_prompt_parts(configurable)
        kb_status = "configured source documents available" if configurable.get("source_document_ids") else "documents may be available"
        fallback_relevance = fast_relevance or ("relevant" if configurable.get("source_document_ids") or has_history else "irrelevant")
        prompt = QUERY_PLANNER_PROMPT.format(
            history=_format_history(messages),
            question=user_message,
            bot_context=parts["bot_context"],
            kb_status=kb_status,
        )

        logger.info(f"[query_planner] Planning query: {user_message!r}")
        response = await llm_service.ainvoke(llm_service.get_llm(structured=False), [HumanMessage(content=prompt)])
        standalone_query, relevance = _parse_plan(message_text(response), user_message, fallback_relevance)
        logger.info(f"[query_planner] standalone={standalone_query!r}, relevance={relevance!r}")
        return {
            "standalone_query": standalone_query,
            "relevance": relevance,
            "token_usage": extract_token_usage(response),
        }
    except Exception as e:
        fallback_relevance = fast_relevance or ("relevant" if configurable.get("source_document_ids") or has_history else "irrelevant")
        logger.error(f"[query_planner] Error: {e} — fallback relevance={fallback_relevance!r}")
        return {"standalone_query": user_message, "relevance": fallback_relevance}
