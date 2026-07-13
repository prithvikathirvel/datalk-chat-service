from pydantic import BaseModel
from typing import TypedDict, Literal, List, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    standalone_query: str
    relevance: Literal["relevant", "irrelevant"]
    final_response: str
    source_documents: List[str]
    retrieved_texts: List[str]
    document_ids: List[str]

class RelevanceCheckOutput(BaseModel):
    relevance: Literal["relevant","irrelevant"]

class GeneralChatOutput(BaseModel):
    response: str