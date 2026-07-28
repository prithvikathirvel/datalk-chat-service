import json
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages as lc_trim_messages


def message_text(response) -> str:
    """Return plain text from provider-specific message content shapes."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "".join(parts)
    return str(content or "")


def extract_token_usage(response) -> dict[str, int]:
    """Extract token counts across OpenAI/Groq/Anthropic-like metadata shapes."""
    usage = getattr(response, "usage_metadata", None) or {}
    meta_usage = (getattr(response, "response_metadata", None) or {}).get("token_usage") or {}
    usage = {**meta_usage, **usage}
    prompt = usage.get("input_tokens") or usage.get("prompt_tokens") or usage.get("prompt_token_count") or 0
    completion = usage.get("output_tokens") or usage.get("completion_tokens") or usage.get("candidates_token_count") or 0
    total = usage.get("total_tokens") or usage.get("total_token_count") or prompt + completion
    return {"prompt_tokens": int(prompt or 0), "completion_tokens": int(completion or 0), "total_tokens": int(total or 0)}


def get_last_human_message(messages: List[BaseMessage]) -> str:
    """Extracts the most recent user message from the message history."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return message_text(m)
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
    """Build compact prompt variables from optional chatbot/runtime config."""
    cfg = (configurable or {}).get("chatbot_config") or {}
    bot_name = str(cfg.get("bot_name") or "Datalk Assistant")[:120]
    fallback = str(
        cfg.get("fallback_message")
        or "I couldn't find that in the available information. Please rephrase or contact support."
    )[:800]

    details = []
    if cfg.get("context_prompt"):
        details.append(f"Configured context/instructions: {str(cfg['context_prompt'])[:1800]}")
    elif cfg.get("bot_description"):
        details.append(f"Business/context: {str(cfg['bot_description'])[:1200]}")
    else:
        details.append(f"Chatbot name: {bot_name}")

    if cfg.get("page_url"):
        details.append(f"Visitor page URL: {str(cfg['page_url'])[:500]}")
    if cfg.get("visitor_email"):
        details.append(f"Visitor email: {str(cfg['visitor_email'])[:320]}")
    if cfg.get("customer_context"):
        raw = cfg["customer_context"]
        details.append(
            "Runtime customer/page context: "
            + (json.dumps(raw, ensure_ascii=False) if isinstance(raw, (dict, list)) else str(raw))[:1200]
        )

    return {
        "bot_name": bot_name,
        "fallback_message": fallback,
        "bot_context": "\n".join(details),
    }