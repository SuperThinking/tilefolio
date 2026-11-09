"""Shared async HTTP client. Uses env-configured CA bundle (SSL_CERT_FILE) via trust_env."""
from __future__ import annotations

from typing import Optional

import httpx

# Honest, generic client name. Don't impersonate browsers to dodge provider limits, and never put
# user identity (emails etc.) in outbound headers. If a free source throttles us, back off (see
# Backoff below) or move to a licensed feed.
USER_AGENT = "Tilefolio/0.1 (self-hosted portfolio viewer)"

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            follow_redirects=True,
            trust_env=True,
        )
    return _client


def set_client(client: httpx.AsyncClient) -> None:
    """Tests inject an httpx.AsyncClient(transport=MockTransport(...))."""
    global _client
    _client = client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class Backoff:
    """Per-provider circuit breaker: after a 429/403, stop calling that provider for a while."""

    def __init__(self, seconds: float = 120.0) -> None:
        self.seconds = seconds
        self.until = 0.0

    def tripped(self) -> bool:
        import time

        return time.monotonic() < self.until

    def trip(self, retry_after: Optional[str] = None) -> None:
        import time

        try:
            wait = float(retry_after) if retry_after else self.seconds
        except ValueError:
            wait = self.seconds
        self.until = time.monotonic() + min(max(wait, 30.0), 900.0)
