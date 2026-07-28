from pydantic import BaseModel, field_validator
from typing import Any, Dict, List, Optional
import re


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[str] = None
    auth_header: Optional[str] = None
    source_document_ids: Optional[List[str]] = None
    """Restricts RAG retrieval to these document IDs when provided (non-empty).
    None/empty = no restriction, search the user's full document corpus.
    Populated server-side for embed widget chats scoped via
    `embed_config_sources` — never trust a client-supplied value here for
    the authenticated `/message` endpoint."""

    # Optional chatbot/runtime context. Widget endpoints populate these from
    # embed config + UI page metadata so the graph can answer as the right bot.
    bot_name: Optional[str] = None
    bot_description: Optional[str] = None
    fallback_message: Optional[str] = None
    page_url: Optional[str] = None
    visitor_email: Optional[str] = None
    customer_context: Optional[Dict[str, Any]] = None

    @field_validator("message")
    @classmethod
    def validate(cls, value):
        if re.search(r"<script.*?>.*?</script>", value, re.IGNORECASE | re.DOTALL):
            raise ValueError("Content contains potentially harmful script tags")
        if "\0" in value:
            raise ValueError("Content contains null bytes")
        return value
