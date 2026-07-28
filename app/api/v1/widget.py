from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from langgraph.graph.state import CompiledStateGraph

from app.api.v1.deps import get_db, get_graph
from app.core.embed_auth import ValidatedEmbedAuth, validate_api_key
from app.core.logging import logger
from app.langraph.graph import execute_graph
from app.model.chat import ChatRequest
from app.schema.embed import (
    EmbedChatRequest,
    EmbedConfigPublic,
    EmbedFeedbackCreate,
    EmbedFeedbackOut,
)
from app.sql.queries import (
    GET_EMBED_CONFIG_SOURCE_IDS,
    INSERT_EMBED_FEEDBACK,
)

widget_router = APIRouter(prefix="/widget", tags=["widget"])


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────


async def _get_source_document_ids(db, config_id: str) -> list[str]:
    rows = await db.execute_async_query(GET_EMBED_CONFIG_SOURCE_IDS, {"config_id": config_id})
    return [row["document_id"] for row in rows]


# ──────────────────────────────────────────────
# Public, API-key-authenticated: widget-facing endpoints
# ──────────────────────────────────────────────


@widget_router.get(
    "/config",
    response_model=EmbedConfigPublic,
    summary="[Public] Fetch a chatbot's public embed configuration",
    description="Authenticated via `X-Api-Key` header or `?apiKey=` query param. No session/JWT required.",
)
async def get_public_embed_config(auth: ValidatedEmbedAuth = Depends(validate_api_key)):
    return EmbedConfigPublic(**auth.config)


@widget_router.post(
    "/chat",
    summary="[Public] Chat with a chatbot from the embedded widget",
    description=(
        "Authenticated via `X-Api-Key` header. Proxies to the same LangGraph pipeline used by the "
        "authenticated `/message` endpoint. If the chatbot has document sources assigned "
        "(`embed_config_sources`), retrieval is restricted to those documents; otherwise the full "
        "document library owned by the chatbot's creator is searched."
    ),
)
async def embed_chat(
    request: Request,
    payload: EmbedChatRequest,
    graph: CompiledStateGraph = Depends(get_graph),
    db=Depends(get_db),
    auth: ValidatedEmbedAuth = Depends(validate_api_key),
):
    start = time.perf_counter()
    try:
        config = auth.config
        source_document_ids = await _get_source_document_ids(db, config["id"])

        query = ChatRequest(
            message=payload.message,
            model=config.get("model"),
            thread_id=payload.thread_id,
            user_id=auth.user_id,
            auth_header=None,
            source_document_ids=source_document_ids or None,
        )
        result = await execute_graph(query, graph)

        response_time_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            f"[embed_chat] config_id={config.get('id')!r} thread_id={result.get('thread_id')!r} "
            f"source_document_ids={source_document_ids!r} response_time_ms={response_time_ms}"
        )

        return {
            "thread_id": result.get("thread_id", ""),
            "final_response": result.get("final_response", ""),
            "source_documents": result.get("source_documents", []),
        }
    except Exception as e:
        logger.error(f"[embed_chat] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {e}")


@widget_router.post(
    "/feedback",
    response_model=EmbedFeedbackOut,
    summary="[Public] Submit feedback from the embedded widget",
    description="Authenticated via `X-Api-Key` header.",
)
async def submit_embed_feedback(
    payload: EmbedFeedbackCreate,
    request: Request,
    db=Depends(get_db),
    auth: ValidatedEmbedAuth = Depends(validate_api_key),
):
    try:
        config = auth.config
        feedback_id = str(uuid.uuid4())
        params = {
            "id": feedback_id,
            "config_id": config["id"],
            "user_id": auth.user_id,
            "thread_id": payload.thread_id,
            "question": payload.question,
            "answer": payload.answer,
            "visitor_email": payload.visitor_email,
            "page_url": payload.page_url,
            "parent_origin": payload.parent_origin or request.headers.get("origin"),
            "reason": payload.reason,
        }
        rows = await db.execute_async_query(INSERT_EMBED_FEEDBACK, params)
        return EmbedFeedbackOut(**rows[0])
    except Exception as e:
        logger.error(f"[submit_embed_feedback] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error submitting feedback: {e}")


@widget_router.get(
    "/script",
    summary="[Public] Fetch the embed bootstrap payload for a chatbot",
    description="Authenticated via `?apiKey=` query param (custom headers aren't practical for a `<script src>` tag). Returns the public config plus the API key so the loaded widget can call `/embed/chat` and `/embed/feedback` directly.",
)
async def get_embed_script_payload(auth: ValidatedEmbedAuth = Depends(validate_api_key)):
    config = EmbedConfigPublic(**auth.config)
    return {"config": config, "endpoints": {"chat": "/widget/chat", "feedback": "/widget/feedback"}}
