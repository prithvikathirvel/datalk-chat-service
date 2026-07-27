"""Embed widget API — chatbot configuration, API keys, public chat & feedback.

This mirrors the "Embed API Key Management & Full Backend Storage" plan:

  * Owner-authenticated endpoints (Cognito JWT via ``get_current_user``)
    manage ``embed_configs`` and rotate ``api_keys`` — these replace the old
    flat-file ``embed-configs.json`` store with real Postgres tables.
  * Public, API-key-authenticated endpoints let the embeddable widget fetch
    its configuration, send chat messages (proxied through the existing
    LangGraph pipeline) and submit feedback — without ever exposing a
    Cognito session to third-party sites.

Routes are mounted under ``{VERSION_PREFIX}/embed`` (see ``app/api/v1/api.py``).
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from langgraph.graph.state import CompiledStateGraph

from app.api.v1.deps import get_db, get_graph
from app.core.api_key import generate_api_key
from app.core.embed_auth import ValidatedEmbedAuth, validate_api_key
from app.core.logging import logger
from app.core.middleware import CurrentUser, get_current_user
from app.langraph.graph import execute_graph
from app.model.chat import ChatRequest
from app.schema.embed import (
    ApiKeyCreated,
    EmbedChatRequest,
    EmbedConfig,
    EmbedConfigCreate,
    EmbedConfigCreateResponse,
    EmbedConfigPublic,
    EmbedConfigUpdate,
    EmbedFeedbackCreate,
    EmbedFeedbackOut,
)
from app.sql.queries import (
    DELETE_EMBED_CONFIG,
    GET_ACTIVE_API_KEYS_BY_CONFIG,
    GET_EMBED_CONFIG_BY_ID,
    GET_EMBED_CONFIG_BY_ID_FOR_USER,
    GET_EMBED_CONFIGS_BY_USER,
    GET_EMBED_FEEDBACK_BY_USER,
    INSERT_API_KEY,
    INSERT_EMBED_CONFIG,
    INSERT_EMBED_FEEDBACK,
    REVOKE_ACTIVE_API_KEYS_FOR_CONFIG,
    UPDATE_EMBED_CONFIG,
)

embed_router = APIRouter(prefix="/embed", tags=["embed"])


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────


async def _get_owned_config_or_404(db, bot_id: str, user_id: str) -> dict:
    rows = await db.execute_async_query(
        GET_EMBED_CONFIG_BY_ID_FOR_USER, {"id": bot_id, "user_id": user_id}
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Embed config not found")
    return rows[0]


async def _create_api_key_for_config(db, config_id: str, user_id: str, name: str = "Default") -> ApiKeyCreated:
    key = generate_api_key()
    rows = await db.execute_async_query(
        INSERT_API_KEY,
        {
            "id": str(uuid.uuid4()),
            "config_id": config_id,
            "user_id": user_id,
            "key_hash": key["hash"],
            "key_prefix": key["prefix"],
            "name": name,
            "expires_at": None,
        },
    )
    row = rows[0]
    return ApiKeyCreated(
        id=row["id"],
        config_id=row["config_id"],
        name=row["name"],
        key_prefix=row["key_prefix"],
        api_key=key["raw"],
        expires_at=row.get("expires_at"),
        created_at=row["created_at"],
    )


# ──────────────────────────────────────────────
# Owner-authenticated: manage embed configs
# ──────────────────────────────────────────────


@embed_router.post(
    "/configs",
    response_model=EmbedConfigCreateResponse,
    summary="Create a chatbot embed configuration",
    description="Creates a new embed config for the authenticated user and generates its first API key. The raw API key is returned only once.",
)
async def create_embed_config(
    payload: EmbedConfigCreate,
    db=Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        config_id = str(uuid.uuid4())
        params = payload.model_dump()
        params["id"] = config_id
        params["user_id"] = user.sub

        rows = await db.execute_async_query(INSERT_EMBED_CONFIG, params)
        config_row = rows[0]

        api_key = await _create_api_key_for_config(db, config_id, user.sub)

        return EmbedConfigCreateResponse(config=EmbedConfig(**config_row), api_key=api_key)
    except Exception as e:
        logger.error(f"[create_embed_config] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating embed config: {e}")


@embed_router.get(
    "/configs",
    response_model=list[EmbedConfig],
    summary="List the authenticated user's chatbot embed configurations",
)
async def list_embed_configs(db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    try:
        rows = await db.execute_async_query(GET_EMBED_CONFIGS_BY_USER, {"user_id": user.sub})
        return [EmbedConfig(**row) for row in rows]
    except Exception as e:
        logger.error(f"[list_embed_configs] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching embed configs: {e}")


@embed_router.get(
    "/configs/{bot_id}",
    response_model=EmbedConfig,
    summary="Get a single chatbot embed configuration",
)
async def get_embed_config(bot_id: str, db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    row = await _get_owned_config_or_404(db, bot_id, user.sub)
    return EmbedConfig(**row)


@embed_router.put(
    "/configs/{bot_id}",
    response_model=EmbedConfig,
    summary="Update a chatbot embed configuration",
    description="Partial update — omitted fields keep their existing values. Does not rotate the API key.",
)
async def update_embed_config(
    bot_id: str,
    payload: EmbedConfigUpdate,
    db=Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    existing = await _get_owned_config_or_404(db, bot_id, user.sub)

    updates = payload.model_dump(exclude_unset=True)
    merged = {**existing, **updates}
    merged["id"] = bot_id
    merged["user_id"] = user.sub

    try:
        rows = await db.execute_async_query(UPDATE_EMBED_CONFIG, merged)
        if not rows:
            raise HTTPException(status_code=404, detail="Embed config not found")
        return EmbedConfig(**rows[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[update_embed_config] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating embed config: {e}")


@embed_router.delete(
    "/configs/{bot_id}",
    summary="Delete a chatbot embed configuration",
    description="Cascades to delete all associated api_keys and embed_feedback rows.",
)
async def delete_embed_config(bot_id: str, db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    try:
        rows = await db.execute_async_query(DELETE_EMBED_CONFIG, {"id": bot_id, "user_id": user.sub})
        if not rows:
            raise HTTPException(status_code=404, detail="Embed config not found")
        return {"success": True, "id": bot_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[delete_embed_config] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting embed config: {e}")


@embed_router.post(
    "/configs/{bot_id}/rotate-key",
    response_model=ApiKeyCreated,
    summary="Rotate the API key for a chatbot embed configuration",
    description="Revokes any currently active key(s) and issues a brand new one. The raw key is returned only once.",
)
async def rotate_api_key(bot_id: str, db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    await _get_owned_config_or_404(db, bot_id, user.sub)
    try:
        await db.execute_async_query(REVOKE_ACTIVE_API_KEYS_FOR_CONFIG, {"config_id": bot_id})
        return await _create_api_key_for_config(db, bot_id, user.sub)
    except Exception as e:
        logger.error(f"[rotate_api_key] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error rotating API key: {e}")


@embed_router.get(
    "/feedback",
    response_model=list[EmbedFeedbackOut],
    summary="List feedback submitted across the authenticated user's chatbots",
)
async def list_embed_feedback(db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    try:
        rows = await db.execute_async_query(GET_EMBED_FEEDBACK_BY_USER, {"user_id": user.sub})
        return [EmbedFeedbackOut(**row) for row in rows]
    except Exception as e:
        logger.error(f"[list_embed_feedback] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching feedback: {e}")


# ──────────────────────────────────────────────
# Public, API-key-authenticated: widget-facing endpoints
# ──────────────────────────────────────────────


@embed_router.get(
    "/config",
    response_model=EmbedConfigPublic,
    summary="[Public] Fetch a chatbot's public embed configuration",
    description="Authenticated via `X-Api-Key` header or `?apiKey=` query param. No session/JWT required.",
)
async def get_public_embed_config(auth: ValidatedEmbedAuth = Depends(validate_api_key)):
    return EmbedConfigPublic(**auth.config)


@embed_router.post(
    "/chat",
    summary="[Public] Chat with a chatbot from the embedded widget",
    description="Authenticated via `X-Api-Key` header. Proxies to the same LangGraph pipeline used by the authenticated `/message` endpoint, scoped to the chatbot owner's documents.",
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
        query = ChatRequest(
            message=payload.message,
            model=config.get("model"),
            thread_id=payload.thread_id,
            user_id=auth.user_id,
            auth_header=None,
        )
        result = await execute_graph(query, graph)

        response_time_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            f"[embed_chat] config_id={config.get('id')!r} thread_id={result.get('thread_id')!r} "
            f"response_time_ms={response_time_ms}"
        )

        return {
            "thread_id": result.get("thread_id", ""),
            "final_response": result.get("final_response", ""),
            "source_documents": result.get("source_documents", []),
        }
    except Exception as e:
        logger.error(f"[embed_chat] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {e}")


@embed_router.post(
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


@embed_router.get(
    "/script",
    summary="[Public] Fetch the embed bootstrap payload for a chatbot",
    description="Authenticated via `?apiKey=` query param (custom headers aren't practical for a `<script src>` tag). Returns the public config plus the API key so the loaded widget can call `/embed/chat` and `/embed/feedback` directly.",
)
async def get_embed_script_payload(auth: ValidatedEmbedAuth = Depends(validate_api_key)):
    config = EmbedConfigPublic(**auth.config)
    return {"config": config, "endpoints": {"chat": "/embed/chat", "feedback": "/embed/feedback"}}
