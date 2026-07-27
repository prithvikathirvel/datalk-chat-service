"""Authentication / authorization helpers for the public embed endpoints.

Unlike the rest of the API (which is protected by Cognito JWTs forwarded via
API Gateway, see ``app.core.middleware.get_current_user``), the embed widget
endpoints are reached directly from third-party websites and cannot carry a
Cognito session. Instead they authenticate with a scoped API key that was
generated when the chatbot's embed config was created (see
``app.core.api_key``).

``validate_api_key`` is meant to be used as a FastAPI dependency on every
public embed route (``/embed/config``, ``/embed/chat``, ``/embed/feedback``):

    1. Read the raw key from the ``X-Api-Key`` header (falls back to the
       ``apiKey`` query parameter for routes such as the embeddable
       ``<script>`` loader where custom headers aren't practical).
    2. Hash it with SHA-256 and look it up in ``api_keys`` joined with
       ``embed_configs``.
    3. Reject if the key is inactive, revoked, or expired.
    4. Reject if the owning config has been deactivated (``is_active``).
    5. Enforce ``allowed_origins`` against the request's ``Origin`` header
       (an empty list means "unrestricted").
    6. Update ``last_used_at`` on the key (best effort, does not block the
       request on failure).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import Depends, Header, HTTPException, Query, Request

from app.api.v1.deps import get_db
from app.core.api_key import hash_api_key
from app.core.logging import logger
from app.sql.queries import GET_CONFIG_AND_KEY_BY_KEY_HASH, UPDATE_API_KEY_LAST_USED


def _extract_origin_host(origin: str) -> tuple[str, str]:
    """Normalize an Origin/allowed-origin value to (scheme, host[:port]).

    Returns ("", host) when no scheme is present so bare hostnames such as
    "example.com" configured in ``allowed_origins`` can match an incoming
    ``https://example.com`` (or any scheme) origin.
    """
    origin = origin.strip().rstrip("/")
    if "://" not in origin:
        return "", origin.lower()
    parsed = urlparse(origin)
    return parsed.scheme.lower(), parsed.netloc.lower()


def _is_origin_allowed(allowed_origins: list[str], request_origin: Optional[str]) -> bool:
    if not allowed_origins:
        # Unrestricted — matches plan: "empty = unrestricted"
        return True
    if "*" in allowed_origins:
        return True
    if not request_origin:
        # Origins are configured but the caller didn't send one (e.g. server
        # to server call, curl, same-origin navigation) — reject to be safe.
        return False

    req_scheme, req_host = _extract_origin_host(request_origin)

    for allowed in allowed_origins:
        if not allowed:
            continue
        allowed_scheme, allowed_host = _extract_origin_host(allowed)
        if allowed_host != req_host:
            continue
        if not allowed_scheme or allowed_scheme == req_scheme:
            return True
    return False


class ValidatedEmbedAuth:
    """Result of a successful API key validation."""

    def __init__(self, config: dict, api_key_id: str, user_id: str):
        self.config = config
        self.api_key_id = api_key_id
        self.user_id = user_id


async def validate_api_key(
    request: Request,
    db=Depends(get_db),
    x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key"),
    api_key_query: Optional[str] = Query(default=None, alias="apiKey"),
) -> ValidatedEmbedAuth:
    raw_key = x_api_key or api_key_query
    if not raw_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_hash = hash_api_key(raw_key)

    rows = await db.execute_async_query(
        GET_CONFIG_AND_KEY_BY_KEY_HASH, {"key_hash": key_hash}
    )
    if not rows:
        logger.warning("[validate_api_key] No config found for supplied API key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    row = rows[0]

    if not row.get("api_key_is_active"):
        raise HTTPException(status_code=401, detail="API key has been revoked")

    if row.get("api_key_revoked_at"):
        raise HTTPException(status_code=401, detail="API key has been revoked")

    expires_at = row.get("api_key_expires_at")
    if expires_at:
        expires_dt = expires_at if isinstance(expires_at, datetime) else datetime.fromisoformat(str(expires_at))
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        if expires_dt < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="API key has expired")

    if not row.get("is_active"):
        raise HTTPException(status_code=403, detail="This chatbot is currently disabled")

    allowed_origins = row.get("allowed_origins") or []
    request_origin = request.headers.get("origin") or request.headers.get("referer")
    if not _is_origin_allowed(allowed_origins, request_origin):
        logger.warning(
            f"[validate_api_key] Origin {request_origin!r} not in allowed_origins for config {row.get('id')!r}"
        )
        raise HTTPException(status_code=403, detail="Origin not allowed for this API key")

    api_key_id = row.get("api_key_id")
    try:
        await db.execute_async_query(UPDATE_API_KEY_LAST_USED, {"id": api_key_id})
    except Exception as e:  # best effort, never block the request on this
        logger.warning(f"[validate_api_key] Failed to update last_used_at: {e}")

    config = {k: v for k, v in row.items() if not k.startswith("api_key_")}
    return ValidatedEmbedAuth(config=config, api_key_id=api_key_id, user_id=row.get("user_id"))
