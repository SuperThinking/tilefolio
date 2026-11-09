"""Instrument master data: NSE equity list, Nifty 500 industries, AMFI schemes.

Used for (a) the symbol picker in "add holding", (b) ISIN -> symbol/scheme resolution
during CSV/CAS import, (c) sector grouping in the treemap.
Refreshed at startup when older than a day; raw files cached under data_dir.
"""
from __future__ import annotations

import csv
import io
import logging
import time
from typing import Dict, List, Optional

from . import db
from .config import settings
from .http import get_client
from .prices import mfnav

log = logging.getLogger(__name__)

NSE_EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
NIFTY500_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
REFRESH_AFTER = 24 * 3600


def _norm_headers(row: Dict[str, str]) -> Dict[str, str]:
    return {(k or "").strip().upper(): (v or "").strip() for k, v in row.items()}


def parse_equity_list(text: str) -> List[tuple]:
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        r = _norm_headers(row)
        sym, name = r.get("SYMBOL"), r.get("NAME OF COMPANY")
        if sym and name:
            out.append((sym, "NSE", name, r.get("ISIN NUMBER") or None))
    return out


def parse_nifty500(text: str) -> Dict[str, str]:
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        r = _norm_headers(row)
        if r.get("SYMBOL") and r.get("INDUSTRY"):
            out[r["SYMBOL"]] = r["INDUSTRY"]
    return out


async def _download(url: str, cache_name: str) -> Optional[str]:
    path = settings.data_dir / cache_name
    if path.exists() and time.time() - path.stat().st_mtime < REFRESH_AFTER:
        return path.read_text()
    try:
        r = await get_client().get(url, timeout=30)
        r.raise_for_status()
        path.write_text(r.text)
        return r.text
    except Exception as e:
        log.warning("download %s failed: %s (using cached copy if any)", url, e)
        return path.read_text() if path.exists() else None


def store_equities(rows: List[tuple], industries: Dict[str, str]) -> None:
    with db.connect() as c:
        c.executemany(
            "INSERT INTO equities(symbol, exchange, name, isin, industry) VALUES(?,?,?,?,?) "
            "ON CONFLICT(exchange, symbol) DO UPDATE SET name=excluded.name, isin=excluded.isin, "
            "industry=COALESCE(excluded.industry, equities.industry)",
            [(s, ex, n, i, industries.get(s)) for (s, ex, n, i) in rows],
        )


async def refresh_all(force: bool = False) -> None:
    last = float(db.get_meta("instruments_refreshed_at") or 0)
    if not force and time.time() - last < REFRESH_AFTER:
        return
    eq = await _download(NSE_EQUITY_URL, "EQUITY_L.csv")
    n500 = await _download(NIFTY500_URL, "ind_nifty500list.csv")
    if eq:
        store_equities(parse_equity_list(eq), parse_nifty500(n500) if n500 else {})
    try:
        await mfnav.refresh_navall()
    except Exception as e:
        log.warning("AMFI NAVAll refresh failed: %s", e)
    db.set_meta("instruments_refreshed_at", str(int(time.time())))


# ---- lookups ---------------------------------------------------------------

def equity_by_isin(isin: str) -> Optional[dict]:
    with db.connect() as c:
        row = c.execute("SELECT * FROM equities WHERE isin = ? LIMIT 1", (isin,)).fetchone()
    return dict(row) if row else None


def equity_by_symbol(symbol: str, exchange: str = "NSE") -> Optional[dict]:
    with db.connect() as c:
        row = c.execute(
            "SELECT * FROM equities WHERE symbol = ? AND exchange = ?", (symbol.upper(), exchange)
        ).fetchone()
    return dict(row) if row else None


def equity_by_name(name: str) -> Optional[dict]:
    """Best-effort match for exports that only carry a company name (e.g. some Groww files)."""
    n = name.strip().upper().replace(" LIMITED", " LTD").rstrip(".")
    with db.connect() as c:
        for row in c.execute("SELECT * FROM equities WHERE UPPER(name) LIKE ? LIMIT 5", (n.split(" LTD")[0] + "%",)):
            return dict(row)
    return None


def search(q: str, kinds: str = "IN_EQ,MF", limit: int = 20) -> List[dict]:
    q = q.strip()
    if len(q) < 2:
        return []
    like = f"%{q.upper()}%"
    out: List[dict] = []
    with db.connect() as c:
        if "IN_EQ" in kinds:
            for r in c.execute(
                "SELECT symbol, exchange, name, isin, industry FROM equities "
                "WHERE symbol LIKE ? OR UPPER(name) LIKE ? "
                "ORDER BY (symbol = ?) DESC, (symbol LIKE ?) DESC, length(symbol) LIMIT ?",
                (like, like, q.upper(), q.upper() + "%", limit),
            ):
                out.append({"type": "IN_EQ", "symbol": r["symbol"], "exchange": r["exchange"],
                            "name": r["name"], "isin": r["isin"], "sector": r["industry"] or ""})
        if "MF" in kinds:
            for r in c.execute(
                "SELECT code, name, isin_growth FROM mf_schemes WHERE UPPER(name) LIKE ? "
                "ORDER BY (UPPER(name) LIKE '%DIRECT%') DESC, length(name) LIMIT ?",
                (like, limit),
            ):
                out.append({"type": "MF", "symbol": r["code"], "exchange": "", "name": r["name"],
                            "isin": r["isin_growth"], "sector": "Mutual Fund"})
    return out[: limit * 2]
