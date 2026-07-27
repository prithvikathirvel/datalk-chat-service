"""CORS handling scoped to the public embed widget routes.

The rest of the API (``/message``, ``/conversation*``, the owner-facing
``/embed/configs*`` routes) is only ever called from our own first-party
frontend and stays untouched by this middleware.

The widget-facing routes (``/embed/config``, ``/embed/chat``,
``/embed/feedback``, ``/embed/script``) are meant to be called directly from
third-party websites embedding the chatbot, so they need permissive CORS at
the transport level. Real access control still happens in
``app.core.embed_auth.validate_api_key`` (API key + ``allowed_origins``
check) — this middleware only makes sure the browser lets the request
through, it does not grant any additional authorization.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_PUBLIC_EMBED_SUFFIXES = ("/embed/config", "/embed/chat", "/embed/feedback", "/embed/script")


def _is_public_embed_path(path: str) -> bool:
    return any(path.rstrip("/") == suffix or path.rstrip("/").endswith(suffix) for suffix in _PUBLIC_EMBED_SUFFIXES) and "/configs" not in path


class EmbedCorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not _is_public_embed_path(path):
            return await call_next(request)

        origin = request.headers.get("origin")

        if request.method == "OPTIONS":
            response = Response(status_code=204)
        else:
            response = await call_next(request)

        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Api-Key, Authorization"
        response.headers["Access-Control-Max-Age"] = "600"
        return response


def add_embed_cors(app):
    app.add_middleware(EmbedCorsMiddleware)
    return app
