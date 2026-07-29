from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Conversation(BaseModel):
    id: UUID = Field(...,description="Unique identifier for the conversation record.")

    thread_id: str = Field(...,description="Unique identifier for the conversation thread.")

    user_id: str = Field(...,description="Authenticated user's unique identifier.")

    chatbot_id: UUID | None = Field(default=None,description="Chatbot identifier.")

    chatbot_name: str | None = Field(default=None,description="Name of the chatbot.")

    user_message: str = Field(...,description="Original message sent by the user.")

    rewritten_query: str | None = Field(default=None,description="Query after rewriting before retrieval.")

    bot_message: str | None = Field(default=None,description="Assistant's response.")

    response_type: Literal["rag", "general_chat"] = Field(...,description="Type of response generated.")

    final_node: str | None = Field(default=None,description="Final LangGraph node that produced the response.")

    # Model
    model: str | None = Field(
        default=None,
        description="LLM model used."
    )

    provider: str | None = Field(
        default=None,
        description="LLM provider (e.g., OpenAI, Anthropic)."
    )

    # Performance
    response_time_ms: Decimal | None = Field(
        default=None,
        ge=0,
        description="Response latency in milliseconds."
    )

    prompt_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Prompt token count."
    )

    completion_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Completion token count."
    )

    total_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Total token count."
    )

    # RAG Analytics
    retrieval_response_time_ms: Decimal | None = Field(
        default=None,
        ge=0,
        description="Time in milliseconds to fetch chunks from the retrieval URL."
    )

    documents_retrieved: int = Field(
        default=0,
        ge=0,
        description="Number of retrieved documents."
    )

    chunks_retrieved: int = Field(
        default=0,
        ge=0,
        description="Number of retrieved chunks."
    )

    confidence_score: Decimal | None = Field(
        default=None,
        description="Confidence score of the generated answer."
    )

    # Status
    is_answered: bool = Field(
        default=True,
        description="Whether the question was answered."
    )

    answer_status: Literal[
        "answered",
        "partial",
        "unanswered",
        "error",
    ] = Field(
        default="answered",
        description="Overall answer status."
    )

    # Feedback
    feedback: Literal[-1, 0, 1] | None = Field(
        default=None,
        description="-1 = thumbs down, 0 = no feedback, 1 = thumbs up."
    )

    feedback_comment: str | None = Field(
        default=None,
        description="Optional user feedback."
    )

    # Errors
    error_message: str | None = Field(
        default=None,
        description="Error message if processing failed."
    )

    # Metadata
    metadata: str | None = Field(
        default=None,
        description="Additional metadata stored as JSON."
    )

    created_at: datetime | None = Field(
        default=None,
        description="Timestamp when the conversation record was created."
    )