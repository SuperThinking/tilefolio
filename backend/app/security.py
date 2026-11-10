"""Request-level controls for the anonymous browser client."""
from __future__ import annotations

import secrets
from typing import Optional, Tuple
from uuid import UUID

from starlette.requests import Request

from .config import settings

CLIENT_UUID_HEADER = "x-client-uuid"
CLIENT_TOKEN_HEADER = "x-tilefolio-client"


def client_uuid(request: Request) -> Optional[str]:
    """Return a canonical UUID sent by the client, or None when it is invalid."""
    raw = request.headers.get(CLIENT_UUID_HEADER, "").strip()
    if not raw:
        return None
    try:
        return str(UUID(raw))
    except (ValueError, AttributeError):
        return None


def access_error(request: Request) -> Optional[Tuple[int, str]]:
    """Return an HTTP error for an API request that is not from the app client."""
    if client_uuid(request) is None:
        return 400, f"{CLIENT_UUID_HEADER} must be a valid UUID"

    # A configured cross-origin deployment must not silently fall back to UUID
    # tracking alone if the production access token was forgotten.
    if settings.cors_origins and not settings.client_token:
        return 503, "Client access is not configured"

    if settings.client_token:
        presented = request.headers.get(CLIENT_TOKEN_HEADER, "")
        if not presented or not secrets.compare_digest(presented, settings.client_token):
            return 403, "Client access token required"

        # A browser Origin is useful as a second, low-cost signal. It is not a
        # cryptographic boundary: non-browser callers can forge it.
        if settings.cors_origins and request.headers.get("origin") not in settings.cors_origins:
            return 403, "Origin is not allowed"

    return None
