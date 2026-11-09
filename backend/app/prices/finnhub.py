"""Finnhub REST quotes for US equities. Free tier: 60 calls/min, personal use.

Enabled only when TF_FINNHUB_API_KEY is set; otherwise US quotes go to Yahoo.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Iterable

from ..config import settings
from ..http import Backoff, get_client
from ..models import Instrument, Quote

log = logging.getLogger(__name__)

QUOTE_URL = "https://finnhub.io/api/v1/quote"
_CONCURRENCY = 5
backoff = Backoff(60)


def enabled() -> bool:
    return bool(settings.finnhub_api_key) and not backoff.tripped()


async def fetch_quotes(instruments: Iterable[Instrument]) -> Dict[str, Quote]:
    sem = asyncio.Semaphore(_CONCURRENCY)
    out: Dict[str, Quote] = {}
    client = get_client()

    async def one(inst: Instrument) -> None:
        if inst.type != "US_EQ":
            return
        async with sem:
            try:
                r = await client.get(
                    QUOTE_URL, params={"symbol": inst.symbol, "token": settings.finnhub_api_key}
                )
            except Exception as e:
                log.info("finnhub %s failed: %s", inst.symbol, e)
                return
        if r.status_code == 429:
            backoff.trip(r.headers.get("retry-after"))
            return
        if r.status_code != 200:
            log.info("finnhub %s -> HTTP %s", inst.symbol, r.status_code)
            return
        j = r.json()
        price = j.get("c")
        if not price:  # Finnhub returns zeros for unknown symbols
            return
        out[inst.key] = Quote(
            key=inst.key,
            price=float(price),
            prev_close=float(j["pc"]) if j.get("pc") else None,
            currency="USD",
            source="finnhub",
            ts=time.time(),
            as_of=str(j.get("t")) if j.get("t") else None,
        )

    await asyncio.gather(*(one(i) for i in instruments))
    return out
