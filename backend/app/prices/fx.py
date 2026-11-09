"""USD/INR: Yahoo INR=X (intraday) with Frankfurter (ECB daily) as fallback."""
from __future__ import annotations

import logging
import time
from typing import Optional

from ..config import settings
from ..http import get_client
from . import yahoo

log = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"

_cache: dict = {"rate": None, "ts": 0.0, "source": None}


async def _frankfurter() -> Optional[float]:
    try:
        r = await get_client().get(FRANKFURTER_URL, params={"base": "USD", "symbols": "INR"})
        if r.status_code == 200:
            return float(r.json()["rates"]["INR"])
    except Exception as e:
        log.info("frankfurter failed: %s", e)
    return None


async def usd_inr() -> dict:
    now = time.time()
    if _cache["rate"] and now - _cache["ts"] < settings.fx_ttl_seconds:
        return dict(_cache)
    rate, source = await yahoo.fetch_fx_usdinr(), "yahoo"
    if not rate:
        rate, source = await _frankfurter(), "frankfurter"
    if rate:
        _cache.update(rate=rate, ts=now, source=source)
    return dict(_cache)  # may be stale (or None) if both sources fail
