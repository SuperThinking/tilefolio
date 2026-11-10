"""Minimal in-memory token-bucket rate limiter (per client IP). Fine for a single process;
replace with a shared store (Redis) if you run multiple workers."""

import time
from typing import Dict, Tuple

from fastapi import HTTPException, Request

from .security import client_uuid


class RateLimiter:
    def __init__(self, rate_per_min: float, burst: int) -> None:
        self.rate = rate_per_min / 60.0
        self.burst = burst
        self._buckets: Dict[str, Tuple[float, float]] = {}

    def check(self, key: str) -> None:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (float(self.burst), now))
        tokens = min(self.burst, tokens + (now - last) * self.rate)
        if tokens < 1:
            raise HTTPException(429, "Too many requests — slow down")
        self._buckets[key] = (tokens - 1, now)
        if len(self._buckets) > 50_000:  # crude memory bound
            self._buckets.clear()

    def __call__(self, request: Request) -> None:
        # Behind a reverse proxy, configure uvicorn --proxy-headers so client.host is the real IP.
        ip = request.client.host if request.client else "unknown"
        # UUID gives independent browser clients fair buckets behind one NAT;
        # retaining the IP keeps UUID rotation from bypassing the whole limiter.
        uuid = client_uuid(request)
        self.check(f"{ip}:{uuid}" if uuid else ip)


quotes_limiter = RateLimiter(rate_per_min=30, burst=10)
upload_limiter = RateLimiter(rate_per_min=10, burst=5)
misc_limiter = RateLimiter(rate_per_min=60, burst=20)
