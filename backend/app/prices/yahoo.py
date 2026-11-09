"""Yahoo Finance chart endpoint (unofficial, personal-use ToS).

We call the public v8 chart endpoint directly instead of depending on yfinance+pandas:
it needs no crumb/cookie and returns price + previous close in `meta`.
Swap this provider for a licensed feed before a commercial launch (see docs/data-sources.md).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Iterable, Optional

from ..http import Backoff, get_client
from ..models import Instrument, Quote

log = logging.getLogger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
_CONCURRENCY = 4
backoff = Backoff(120)


def yahoo_symbol(inst: Instrument) -> Optional[str]:
    if inst.type == "IN_EQ":
        suffix = ".BO" if inst.exchange == "BSE" else ".NS"
        return inst.symbol + suffix
    if inst.type == "US_EQ":
        return inst.symbol.replace(".", "-")  # BRK.B -> BRK-B
    return None


def parse_chart(payload: dict) -> Optional[dict]:
    try:
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            return None
        meta = result[0]["meta"]
        price = meta.get("regularMarketPrice")
        if price is None:
            return None
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        return {
            "price": float(price),
            "prev_close": float(prev) if prev else None,
            "currency": meta.get("currency") or "",
            "as_of": meta.get("regularMarketTime"),
        }
    except (KeyError, TypeError, ValueError, IndexError):
        return None


async def fetch_symbol(sym: str) -> Optional[dict]:
    if backoff.tripped():
        return None
    client = get_client()
    r = await client.get(CHART_URL.format(sym=sym), params={"range": "1d", "interval": "1d"})
    if r.status_code in (403, 429):
        log.warning("yahoo throttled (HTTP %s); backing off", r.status_code)
        backoff.trip(r.headers.get("retry-after"))
        return None
    if r.status_code != 200:
        log.info("yahoo %s -> HTTP %s", sym, r.status_code)
        return None
    return parse_chart(r.json())


async def fetch_quotes(instruments: Iterable[Instrument]) -> Dict[str, Quote]:
    sem = asyncio.Semaphore(_CONCURRENCY)
    out: Dict[str, Quote] = {}

    async def one(inst: Instrument) -> None:
        sym = yahoo_symbol(inst)
        if not sym:
            return
        async with sem:
            try:
                data = await fetch_symbol(sym)
            except Exception as e:  # network errors shouldn't sink the batch
                log.info("yahoo %s failed: %s", sym, e)
                return
        if data:
            default_ccy = "INR" if inst.type == "IN_EQ" else "USD"
            out[inst.key] = Quote(
                key=inst.key,
                price=data["price"],
                prev_close=data["prev_close"],
                currency=data["currency"] or default_ccy,
                source="yahoo",
                ts=time.time(),
                as_of=str(data["as_of"]) if data["as_of"] else None,
            )

    await asyncio.gather(*(one(i) for i in instruments))
    return out


async def fetch_fx_usdinr() -> Optional[float]:
    try:
        data = await fetch_symbol("INR=X")
        return data["price"] if data else None
    except Exception as e:
        log.info("yahoo fx failed: %s", e)
        return None
