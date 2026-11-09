"""Upstox API v2 — bring-your-own-key holdings sync (OAuth2 authorization-code).

Each user creates their own Upstox developer app with redirect URI <origin>/connect/upstox.
Stateless: client_secret and tokens are never stored or logged. Tokens expire ~3:30 AM daily.
"""
from __future__ import annotations

from typing import List
from urllib.parse import urlencode

from ..http import get_client
from ..importers.csv_import import resolve
from ..models import Holding, ImportResult
from .kite import BrokerError

API = "https://api.upstox.com/v2"


def login_url(client_id: str, redirect_uri: str) -> str:
    q = urlencode({"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri})
    return f"{API}/login/authorization/dialog?{q}"


async def _token(client_id: str, client_secret: str, code: str, redirect_uri: str) -> str:
    r = await get_client().post(
        f"{API}/login/authorization/token",
        headers={"Accept": "application/json"},
        data={"code": code, "client_id": client_id, "client_secret": client_secret,
              "redirect_uri": redirect_uri, "grant_type": "authorization_code"},
    )
    try:
        j = r.json()
    except ValueError:
        j = {}
    if r.status_code != 200 or "access_token" not in j:
        errs = j.get("errors") or [{}]
        raise BrokerError(errs[0].get("message") or f"Upstox login failed (HTTP {r.status_code})")
    return j["access_token"]


def map_holdings(rows: List[dict]) -> List[Holding]:
    out = []
    for h in rows:
        qty = float(h.get("quantity") or 0) + float(h.get("t1_quantity") or 0)
        if qty <= 0:
            continue
        out.append(Holding(
            type="IN_EQ", symbol=h.get("tradingsymbol") or "", exchange=h.get("exchange") or "NSE",
            qty=qty, avg_price=float(h.get("average_price") or 0), isin=h.get("isin") or "",
            name=h.get("company_name") or "", broker="Upstox",
        ))
    return out


async def fetch_holdings(client_id: str, client_secret: str, code: str, redirect_uri: str) -> ImportResult:
    token = await _token(client_id, client_secret, code, redirect_uri)
    r = await get_client().get(
        f"{API}/portfolio/long-term-holdings",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if r.status_code != 200:
        raise BrokerError(f"Upstox holdings failed (HTTP {r.status_code})")
    res = ImportResult(holdings=map_holdings(r.json().get("data") or []), source="upstox")
    for h in res.holdings:
        w = resolve(h)
        if w:
            res.warnings.append(w)
    return res
