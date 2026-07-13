from langchain_core.messages import BaseMessage, HumanMessage
from typing import List

def get_last_human_message(messages: List[BaseMessage]) -> str:
    """Extracts the most recent user message from the message history."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


def trim_messages(messages: List[BaseMessage], max_messages: int = 10) -> List[BaseMessage]:
    """Returns the last max_messages messages to bound token usage in long threads."""
    return messages[-max_messages:] if len(messages) > max_messages else messages