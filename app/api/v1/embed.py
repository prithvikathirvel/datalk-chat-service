from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.deps import get_db
from app.core.api_key import generate_api_key
from app.core.logging import logger
from app.core.middleware import CurrentUser, get_current_user
from app.schema.embed import (
    ApiKeyCreated,
    EmbedConfig,
    EmbedConfigCreate,
    EmbedConfigCreateResponse,
    EmbedConfigSource,
    EmbedConfigSourcesAdd,
    EmbedConfigUpdate,
    EmbedFeedbackOut,
)
from app.sql.queries import (
    DELETE_ALL_EMBED_CONFIG_SOURCES,
    DELETE_EMBED_CONFIG,
    DELETE_EMBED_CONFIG_SOURCE,
    GET_EMBED_CONFIG_BY_ID_FOR_USER,
    GET_EMBED_CONFIG_SOURCE_IDS,
    GET_EMBED_CONFIG_SOURCES,
    GET_EMBED_CONFIGS_BY_USER,
    GET_EMBED_FEEDBACK_BY_USER,
    INSERT_API_KEY,
    INSERT_EMBED_CONFIG,
    REVOKE_ACTIVE_API_KEYS_FOR_CONFIG,
    UPDATE_EMBED_CONFIG,
    UPSERT_EMBED_CONFIG_SOURCE,
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


async def _get_source_document_ids(db, config_id: str) -> list[str]:
    rows = await db.execute_async_query(GET_EMBED_CONFIG_SOURCE_IDS, {"config_id": config_id})
    return [row["document_id"] for row in rows]


async def _to_embed_config(db, row: dict) -> EmbedConfig:
    """Hydrate a raw ``embed_configs`` row with its scoped source document IDs."""
    source_document_ids = await _get_source_document_ids(db, row["id"])
    return EmbedConfig(**row, source_document_ids=source_document_ids)


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

        return EmbedConfigCreateResponse(config=await _to_embed_config(db, config_row), api_key=api_key)
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
        return [await _to_embed_config(db, row) for row in rows]
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
    return await _to_embed_config(db, row)


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
        return await _to_embed_config(db, rows[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[update_embed_config] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating embed config: {e}")


@embed_router.delete(
    "/configs/{bot_id}",
    summary="Delete a chatbot embed configuration",
    description="Cascades to delete all associated api_keys, embed_feedback and embed_config_sources rows.",
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
# Owner-authenticated: per-chatbot document sources (RAG scoping)
# ──────────────────────────────────────────────


@embed_router.get(
    "/configs/{bot_id}/sources",
    response_model=list[EmbedConfigSource],
    summary="List documents assigned as RAG sources for a chatbot",
    description="Empty result means the chatbot searches the user's entire document library (no restriction).",
)
async def list_embed_config_sources(bot_id: str, db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    await _get_owned_config_or_404(db, bot_id, user.sub)
    try:
        rows = await db.execute_async_query(GET_EMBED_CONFIG_SOURCES, {"config_id": bot_id})
        return [EmbedConfigSource(**row) for row in rows]
    except Exception as e:
        logger.error(f"[list_embed_config_sources] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching sources: {e}")


@embed_router.post(
    "/configs/{bot_id}/sources",
    response_model=list[EmbedConfigSource],
    summary="Assign one or more documents as RAG sources for a chatbot",
    description="Upserts each document — safe to call repeatedly. Does not remove documents omitted from the payload; use DELETE to remove.",
)
async def add_embed_config_sources(
    bot_id: str,
    payload: EmbedConfigSourcesAdd,
    db=Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    await _get_owned_config_or_404(db, bot_id, user.sub)
    try:
        results = []
        for doc in payload.documents:
            rows = await db.execute_async_query(
                UPSERT_EMBED_CONFIG_SOURCE,
                {
                    "config_id": bot_id,
                    "document_id": doc.document_id,
                    "document_filename": doc.document_filename,
                },
            )
            results.append(EmbedConfigSource(**rows[0]))
        return results
    except Exception as e:
        logger.error(f"[add_embed_config_sources] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding sources: {e}")


@embed_router.delete(
    "/configs/{bot_id}/sources/{document_id}",
    summary="Remove a single document source from a chatbot",
)
async def delete_embed_config_source(
    bot_id: str,
    document_id: str,
    db=Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    await _get_owned_config_or_404(db, bot_id, user.sub)
    try:
        rows = await db.execute_async_query(
            DELETE_EMBED_CONFIG_SOURCE, {"config_id": bot_id, "document_id": document_id}
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Source document not found for this chatbot")
        return {"success": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[delete_embed_config_source] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error removing source: {e}")


@embed_router.delete(
    "/configs/{bot_id}/sources",
    summary="Clear all document sources for a chatbot",
    description="Reverts the chatbot to 'all documents' mode (no RAG restriction).",
)
async def clear_embed_config_sources(bot_id: str, db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    await _get_owned_config_or_404(db, bot_id, user.sub)
    try:
        rows = await db.execute_async_query(DELETE_ALL_EMBED_CONFIG_SOURCES, {"config_id": bot_id})
        return {"success": True, "removed": len(rows)}
    except Exception as e:
        logger.error(f"[clear_embed_config_sources] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing sources: {e}")


