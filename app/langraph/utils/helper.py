from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from typing import List


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


def trim_messages(messages: List[BaseMessage], max_messages: int = 10) -> List[BaseMessage]:
    """Returns the last max_messages messages to bound token usage in long threads."""
    return messages[-max_messages:] if len(messages) > max_messages else messages