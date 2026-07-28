import json
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages as lc_trim_messages


def extract_token_usage(response) -> dict[str, int]:
    """Extract token counts from an AIMessage's usage_metadata (provider-agnostic)."""
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def get_last_human_message(messages: List[BaseMessage]) -> str:
    """Extracts the most recent user message from the message history."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


def trim_messages(messages: List[BaseMessage], max_messages: int = 10, max_tokens: int = 2500) -> List[BaseMessage]:
    """Token-aware trimming with a simple message-count fallback."""
    try:
        return lc_trim_messages(
            messages,
            strategy="last",
            token_counter=count_tokens_approximately,
            max_tokens=max_tokens,
            start_on="human",
            end_on=("human", "ai"),
        )
    except Exception:
        return messages[-max_messages:] if len(messages) > max_messages else messages


def get_chatbot_prompt_parts(configurable: dict | None) -> dict[str, str]:
    """Build small prompt variables from optional chatbot/runtime config."""
    cfg = (configurable or {}).get("chatbot_config") or {}
    bot_name = str(cfg.get("bot_name") or "Datalk Assistant")[:120]
    fallback = str(
        cfg.get("fallback_message")
        or "I couldn't find that in the available information. Please rephrase or contact support."
    )[:800]

    details = []
    if cfg.get("bot_description"):
        details.append(f"Business/context/instructions: {str(cfg['bot_description'])[:1500]}")
    if cfg.get("page_url"):
        details.append(f"Visitor page URL: {str(cfg['page_url'])[:500]}")
    if cfg.get("visitor_email"):
        details.append(f"Visitor email: {str(cfg['visitor_email'])[:320]}")
    if cfg.get("customer_context"):
        raw = cfg["customer_context"]
        details.append(
            "Runtime customer/page context: "
            + (json.dumps(raw, ensure_ascii=False) if isinstance(raw, (dict, list)) else str(raw))[:1500]
        )

    return {
        "bot_name": bot_name,
        "fallback_message": fallback,
        "bot_context": "\n".join(details) if details else "No additional customer context provided.",
    }