from langchain_core.messages import BaseMessage, HumanMessage
from typing import List
def get_last_human_message(messages: List[BaseMessage]) -> str:
    """Extracts the most recent user message from the message history."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return ""