"""Indian mutual-fund NAVs.

Primary: AMFI NAVAll.txt (all schemes, latest NAV only). We snapshot it into `nav_history`
on every refresh so day change = latest vs previous stored NAV.
Fallback/backfill: mfapi.in /mf/{code} (full history, newest first) when we have < 2 snapshots.

NAVs publish in the evening, so MF "day change" reflects the last NAV date, not intraday.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from .. import db
from ..http import get_client
from ..models import Instrument, Quote

log = logging.getLogger(__name__)

NAVALL_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
MFAPI_URL = "https://api.mfapi.in/mf/{code}"


def _iso(d: str) -> Optional[str]:
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(d.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _isin(v: str) -> Optional[str]:
    v = v.strip()
    return v if len(v) == 12 and v.startswith("INF") else None


def parse_navall(text: str) -> List[Tuple[str, str, Optional[str], Optional[str], Optional[float], Optional[str]]]:
    """Returns rows of (code, name, isin_growth, isin_reinv, nav, iso_date).

    Format: `Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;NAV;Date`
    interleaved with fund-house / category header lines that contain no ';'.
    """
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 6 or not parts[0].isdigit():
            continue
        code, isin_g, isin_r, name = parts[0], parts[1], parts[2], parts[3]
        nav_s, date_s = parts[-2], parts[-1]
        try:
            nav: Optional[float] = float(nav_s)
        except ValueError:
            nav = None
        rows.append((code, name, _isin(isin_g), _isin(isin_r), nav, _iso(date_s)))
    return rows


def store_navall(rows) -> int:
    with db.connect() as c:
        c.executemany(
            "INSERT INTO mf_schemes(code, name, isin_growth, isin_reinv) VALUES(?,?,?,?) "
            "ON CONFLICT(code) DO UPDATE SET name=excluded.name, isin_growth=excluded.isin_growth, "
            "isin_reinv=excluded.isin_reinv",
            [(r[0], r[1], r[2], r[3]) for r in rows],
        )
        navs = [(r[0], r[5], r[4]) for r in rows if r[4] is not None and r[5]]
        c.executemany("INSERT OR REPLACE INTO nav_history(code, nav_date, nav) VALUES(?,?,?)", navs)
        # Keep history bounded: ~10 latest NAV dates per scheme is plenty for day change.
        c.execute(
            "DELETE FROM nav_history WHERE nav_date < date('now', '-30 days')"
        )
    return len(rows)


async def refresh_navall() -> int:
    client = get_client()
    r = await client.get(NAVALL_URL, timeout=60)
    r.raise_for_status()
    rows = parse_navall(r.text)
    n = store_navall(rows)
    db.set_meta("navall_refreshed_at", str(int(time.time())))
    log.info("AMFI NAVAll: stored %d schemes", n)
    return n


def _latest_two(code: str) -> List[Tuple[str, float]]:
    with db.connect() as c:
        rows = c.execute(
            "SELECT nav_date, nav FROM nav_history WHERE code = ? ORDER BY nav_date DESC LIMIT 2", (code,)
        ).fetchall()
    return [(r["nav_date"], r["nav"]) for r in rows]


async def _backfill_mfapi(code: str) -> None:
    client = get_client()
    try:
        r = await client.get(MFAPI_URL.format(code=code))
        if r.status_code != 200:
            return
        j = r.json()
    except Exception as e:
        log.info("mfapi %s failed: %s", code, e)
        return
    data = (j.get("data") or [])[:5]
    rows = []
    for d in data:
        iso = _iso(d.get("date", ""))
        try:
            nav = float(d.get("nav"))
        except (TypeError, ValueError):
            continue
        if iso:
            rows.append((code, iso, nav))
    name = (j.get("meta") or {}).get("scheme_name")
    with db.connect() as c:
        c.executemany("INSERT OR REPLACE INTO nav_history(code, nav_date, nav) VALUES(?,?,?)", rows)
        if name:
            c.execute(
                "INSERT INTO mf_schemes(code, name) VALUES(?, ?) ON CONFLICT(code) DO NOTHING", (code, name)
            )


async def fetch_quotes(instruments: Iterable[Instrument]) -> Dict[str, Quote]:
    out: Dict[str, Quote] = {}
    for inst in instruments:
        if inst.type != "MF":
            continue
        rows = _latest_two(inst.symbol)
        if len(rows) < 2:
            await _backfill_mfapi(inst.symbol)
            rows = _latest_two(inst.symbol)
        if not rows:
            continue
        (d0, nav0) = rows[0]
        prev = rows[1][1] if len(rows) > 1 else None
        out[inst.key] = Quote(
            key=inst.key, price=nav0, prev_close=prev, currency="INR",
            source="amfi", ts=time.time(), as_of=d0,
        )
    return out


def code_for_isin(isin: str) -> Optional[str]:
    with db.connect() as c:
        row = c.execute(
            "SELECT code FROM mf_schemes WHERE isin_growth = ? OR isin_reinv = ? LIMIT 1", (isin, isin)
        ).fetchone()
    return row["code"] if row else None
