"""Zerodha Kite Connect — bring-your-own-key holdings sync.

Why BYO-key: Kite apps are limited to a single Zerodha user ID unless approved for
multi-user use (see docs/data-sources.md). Each user creates a free "Kite Connect Personal" app,
sets its redirect URL to  <origin>/connect/kite  and pastes api_key + api_secret into settings
(stored in their browser only).

Stateless: secrets and tokens pass through this request and are never stored or logged.
"""
from __future__ import annotations

import hashlib
from typing import List

from ..http import get_client
from ..importers.csv_import import resolve
from ..models import Holding, ImportResult

API = "https://api.kite.trade"
HEADERS = {"X-Kite-Version": "3"}


def login_url(api_key: str) -> str:
    return f"https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"


def checksum(api_key: str, request_token: str, api_secret: str) -> str:
    return hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode()).hexdigest()


class BrokerError(Exception):
    pass


async def _session(api_key: str, api_secret: str, request_token: str) -> str:
    r = await get_client().post(
        f"{API}/session/token",
        headers=HEADERS,
        data={"api_key": api_key, "request_token": request_token,
              "checksum": checksum(api_key, request_token, api_secret)},
    )
    j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or j.get("status") != "success":
        raise BrokerError(j.get("message") or f"Kite login failed (HTTP {r.status_code})")
    return j["data"]["access_token"]


def map_equity(rows: List[dict]) -> List[Holding]:
    out = []
    for h in rows:
        qty = float(h.get("quantity") or 0) + float(h.get("t1_quantity") or 0)
        if qty <= 0:
            continue
        out.append(Holding(
            type="IN_EQ", symbol=h.get("tradingsymbol", ""), exchange=h.get("exchange") or "NSE",
            qty=qty, avg_price=float(h.get("average_price") or 0), isin=h.get("isin") or "",
            broker="Zerodha",
        ))
    return out


def map_mf(rows: List[dict]) -> List[Holding]:
    out = []
    for h in rows:
        qty = float(h.get("quantity") or 0)
        if qty <= 0:
            continue
        out.append(Holding(
            type="MF", symbol="", isin=h.get("tradingsymbol") or "", name=h.get("fund") or "",
            qty=qty, avg_price=float(h.get("average_price") or 0), broker="Zerodha",
        ))
    return out


async def fetch_holdings(api_key: str, api_secret: str, request_token: str) -> ImportResult:
    token = await _session(api_key, api_secret, request_token)
    auth = {**HEADERS, "Authorization": f"token {api_key}:{token}"}
    client = get_client()
    res = ImportResult(holdings=[], source="kite")

    r = await client.get(f"{API}/portfolio/holdings", headers=auth)
    if r.status_code != 200:
        raise BrokerError(f"Kite holdings failed (HTTP {r.status_code})")
    res.holdings += map_equity(r.json().get("data") or [])

    r = await client.get(f"{API}/mf/holdings", headers=auth)
    if r.status_code == 200:
        res.holdings += map_mf(r.json().get("data") or [])
    else:
        res.warnings.append("Kite MF holdings unavailable for this app — use CAS import for funds.")

    for h in res.holdings:
        w = resolve(h)
        if w:
            res.warnings.append(w)
    return res
