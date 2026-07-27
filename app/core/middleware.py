import json
import logging
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CurrentUser(BaseModel):
    sub: str
    email: str | None = None
    username: str | None = None
    groups: list[str] = []


def get_current_user(request: Request) -> CurrentUser:
    request_context = request.headers.get("x-amzn-request-context")

    if not request_context:
        logger.warning("Missing x-amzn-request-context header")
        raise HTTPException(
            status_code=401,
            detail="Unable to retrieve user information",
        )

    try:
        context: dict[str, Any] = json.loads(request_context)
    except json.JSONDecodeError:
        logger.warning("Malformed x-amzn-request-context header: %s", request_context)
        raise HTTPException(
            status_code=401,
            detail="Unable to retrieve user information",
        )

    claims = (
        context.get("authorizer", {})
               .get("jwt", {})
               .get("claims", {})
    )

    sub = claims.get("sub")
    if not sub:
        logger.warning("No sub claim in JWT authorizer context: %s", claims)
        raise HTTPException(
            status_code=401,
            detail="Unable to retrieve user information",
        )

    groups = claims.get("cognito:groups", [])
    if isinstance(groups, str):
        groups = [g.strip() for g in groups.split(",")]

    return CurrentUser(
        sub=sub,
        email=claims.get("email"),
        username=claims.get("username"),
        groups=groups,
    )