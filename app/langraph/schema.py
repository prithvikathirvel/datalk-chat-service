from pydantic import BaseModel, Field
from typing import TypedDict, Literal, List, Annotated, Dict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def _add_token_usage(
    current: Dict[str, int] | None, update: Dict[str, int]
) -> Dict[str, int]:
    """Reducer that accumulates token counts across all graph nodes."""
    base = current or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": base.get("prompt_tokens", 0) + update.get("prompt_tokens", 0),
        "completion_tokens": base.get("completion_tokens", 0) + update.get("completion_tokens", 0),
        "total_tokens": base.get("total_tokens", 0) + update.get("total_tokens", 0),
    }


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    standalone_query: str
    relevance: Literal["relevant", "irrelevant"]
    final_response: str
    source_documents: List[str]
    retrieved_texts: List[str]
    document_ids: List[str]
    token_usage: Annotated[Dict[str, int], _add_token_usage]
    retrieval_response_time_ms: float


class QueryPlanOutput(BaseModel):
    standalone_query: str = Field(
        description="Self-contained latest user request preserving every entity, constraint, and sub-question."
    )
    relevance: Literal["relevant", "irrelevant"] = Field(
        description="relevant when retrieval/customer knowledge is needed; otherwise irrelevant."
    )


class RelevanceCheckOutput(BaseModel):
    relevance: Literal["relevant", "irrelevant"]


class GeneralChatOutput(BaseModel):
    response: str