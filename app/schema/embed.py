"""Pydantic schemas for the embed widget feature set.

Covers three DB-backed resources:
  * ``embed_configs``  — chatbot / widget configuration owned by a user.
  * ``api_keys``       — scoped keys used to authenticate the public widget.
  * ``embed_feedback`` — feedback submitted from an embedded widget.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

LauncherStyle = Literal["circle", "rounded", "square"]
FeedbackReason = Literal["not_helpful", "needs_human", "gap_detected"]


class EmbedConfigBase(BaseModel):
    """Fields that make up a chatbot's embed configuration."""

    bot_name: str = Field(..., min_length=1, max_length=200)
    bot_description: Optional[str] = None

    welcome_message: str = Field(..., min_length=1)
    fallback_message: str = Field(..., min_length=1)
    suggested_questions: List[str] = Field(default_factory=list)

    primary_color: str = Field(default="#0f172a")
    chat_background: Optional[str] = None
    position: str = Field(default="bottom-right")
    launcher_label: str = Field(default="Chat")
    launcher_style: Optional[LauncherStyle] = "circle"
    avatar_initials: str = Field(..., min_length=1, max_length=4)
    border_radius_style: Optional[str] = "rounded"
    widget_shadow: Optional[str] = "soft"
    font_family: Optional[str] = "system"
    show_powered_by: bool = True

    allowed_origins: List[str] = Field(default_factory=list)
    collect_visitor_email: bool = False
    is_active: bool = True
    model: Optional[str] = None

    @field_validator("suggested_questions", "allowed_origins", mode="before")
    @classmethod
    def _coerce_none_to_list(cls, value):
        return value if value is not None else []


class EmbedConfigCreate(EmbedConfigBase):
    """Payload for ``POST /embed/configs``."""


class EmbedConfigUpdate(BaseModel):
    """Payload for ``PUT /embed/configs/{bot_id}``.

    Every field is optional — only the supplied fields are updated, existing
    values are preserved for anything omitted.
    """

    bot_name: Optional[str] = None
    bot_description: Optional[str] = None

    welcome_message: Optional[str] = None
    fallback_message: Optional[str] = None
    suggested_questions: Optional[List[str]] = None

    primary_color: Optional[str] = None
    chat_background: Optional[str] = None
    position: Optional[str] = None
    launcher_label: Optional[str] = None
    launcher_style: Optional[LauncherStyle] = None
    avatar_initials: Optional[str] = None
    border_radius_style: Optional[str] = None
    widget_shadow: Optional[str] = None
    font_family: Optional[str] = None
    show_powered_by: Optional[bool] = None

    allowed_origins: Optional[List[str]] = None
    collect_visitor_email: Optional[bool] = None
    is_active: Optional[bool] = None
    model: Optional[str] = None


class EmbedConfig(EmbedConfigBase):
    """Full DB representation returned to the authenticated owner."""

    id: UUID
    user_id: str
    source_document_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EmbedConfigPublic(EmbedConfigBase):
    """Sanitized representation returned to the public widget.

    Excludes ``user_id``, ``source_document_ids`` and any other
    internal/owner-only fields — the widget doesn't need to know which
    documents back its answers, only the chat/feedback endpoints need that
    (resolved server-side from ``embed_config_sources``).
    """

    id: UUID


class ApiKeyCreated(BaseModel):
    """Returned exactly once, right after creation/rotation."""

    id: UUID
    config_id: UUID
    name: str
    key_prefix: str
    api_key: str  # raw key — shown once, never stored
    expires_at: Optional[datetime] = None
    created_at: datetime


class ApiKeyOut(BaseModel):
    """Masked representation safe to list/display repeatedly."""

    id: UUID
    config_id: UUID
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime


class EmbedConfigCreateResponse(BaseModel):
    """Response body for ``POST /embed/configs``."""

    config: EmbedConfig
    api_key: ApiKeyCreated


class EmbedFeedbackCreate(BaseModel):
    thread_id: Optional[str] = None
    question: str = Field(..., min_length=1)
    answer: Optional[str] = None
    visitor_email: Optional[EmailStr] = None
    page_url: Optional[str] = None
    parent_origin: Optional[str] = None
    reason: FeedbackReason


class EmbedFeedbackOut(BaseModel):
    id: UUID
    config_id: UUID
    user_id: str
    thread_id: Optional[str] = None
    question: str
    answer: Optional[str] = None
    visitor_email: Optional[str] = None
    page_url: Optional[str] = None
    parent_origin: Optional[str] = None
    reason: FeedbackReason
    created_at: datetime


class EmbedChatRequest(BaseModel):
    """Payload for the public, API-key-authenticated ``/embed/chat`` route."""

    message: str = Field(..., min_length=1)
    thread_id: Optional[str] = None
    visitor_email: Optional[EmailStr] = None
    page_url: Optional[str] = None


class EmbedConfigSourceIn(BaseModel):
    """A single document to attach as a RAG source for a chatbot."""

    document_id: str = Field(..., min_length=1)
    document_filename: str = Field(..., min_length=1)


class EmbedConfigSourcesAdd(BaseModel):
    """Payload for ``POST /embed/configs/{bot_id}/sources``."""

    documents: List[EmbedConfigSourceIn] = Field(..., min_length=1)


class EmbedConfigSource(BaseModel):
    """DB representation of an assigned source document."""

    config_id: UUID
    document_id: str
    document_filename: str
    added_at: datetime

