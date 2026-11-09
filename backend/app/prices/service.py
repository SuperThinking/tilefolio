"""Quote service: shared TTL cache across all users + provider routing with fallback.

Routing:
    IN_EQ -> yahoo
    US_EQ -> finnhub (if key) -> yahoo fallback for misses
    MF    -> amfi snapshots (+ mfapi backfill)
To add a provider: write `async fetch_quotes(instruments) -> {key: Quote}` and add it to ROUTES.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Dict, Iterable, List

from ..config import settings
from ..models import Instrument, Quote
from . import finnhub, mfnav, yahoo

Fetcher = Callable[[List[Instrument]], Awaitable[Dict[str, Quote]]]


def _routes() -> Dict[str, List[Fetcher]]:
    us: List[Fetcher] = [finnhub.fetch_quotes, yahoo.fetch_quotes] if finnhub.enabled() else [yahoo.fetch_quotes]
    return {
        "IN_EQ": [yahoo.fetch_quotes],
        "US_EQ": us,
        "MF": [mfnav.fetch_quotes],
    }


class QuoteCache:
    def __init__(self) -> None:
        self._data: Dict[str, Quote] = {}
        self._lock = asyncio.Lock()

    def fresh(self, key: str, ttl: float) -> bool:
        q = self._data.get(key)
        return q is not None and time.time() - q.ts < ttl

    def get(self, key: str):
        return self._data.get(key)

    def put_many(self, quotes: Dict[str, Quote]) -> None:
        self._data.update(quotes)

    def clear(self) -> None:
        self._data.clear()


cache = QuoteCache()


def _ttl(inst: Instrument) -> float:
    # NAVs change once a day; no point re-querying the DB every 45s.
    return 900.0 if inst.type == "MF" else float(settings.quote_ttl_seconds)


async def get_quotes(instruments: Iterable[Instrument]) -> Dict[str, Quote]:
    insts = {i.key: i for i in instruments if i.type != "OTHER"}
    async with cache._lock:  # serialise refreshes so concurrent users don't stampede providers
        stale = [i for k, i in insts.items() if not cache.fresh(k, _ttl(i))]
        by_type: Dict[str, List[Instrument]] = {}
        for i in stale:
            by_type.setdefault(i.type, []).append(i)

        async def run_chain(t: str, pending: List[Instrument]) -> Dict[str, Quote]:
            got: Dict[str, Quote] = {}
            for fetcher in _routes().get(t, []):
                if not pending:
                    break
                res = await fetcher(pending)
                got.update(res)
                pending = [i for i in pending if i.key not in res]
            return got

        results = await asyncio.gather(*(run_chain(t, lst) for t, lst in by_type.items()))
        for r in results:
            cache.put_many(r)
    # Serve stale-but-present quotes rather than nothing when providers fail.
    return {k: cache.get(k) for k in insts if cache.get(k) is not None}
