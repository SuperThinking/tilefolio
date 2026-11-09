"""Generic holdings parser for broker CSV/XLSX exports.

Strategy: find the header row (exports often have preamble rows), map columns via exact
alias matching on normalised header names, then resolve each row to an instrument using
symbol -> ISIN -> name, in that order, against the instrument master.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Dict, List, Optional, Sequence

from .. import instruments
from ..models import Holding, ImportResult
from ..prices import mfnav
from .presets import PRESETS

# Order matters: earlier aliases win when several columns match the same role.
ALIASES: Dict[str, List[str]] = {
    "symbol": ["symbol", "tradingsymbol", "trading symbol", "instrument", "ticker", "scrip",
               "scrip name", "stock symbol", "nse symbol", "scheme code", "amfi code"],
    "name": ["stock name", "company name", "scheme name", "fund name", "security name",
             "name", "company", "stock", "scheme"],
    "isin": ["isin", "isin code", "isin number", "isin no"],
    "qty": ["quantity available", "qty", "quantity", "units", "balance units", "shares",
            "no of shares", "net qty", "holding qty", "total quantity", "free qty", "current units"],
    "avg": ["avg price", "avg cost", "average price", "average buy price", "avg buy price",
            "buy avg", "buy average", "average cost", "average cost price", "buy price",
            "cost price", "avg nav", "average nav", "purchase price", "average purchase price"],
    "invested": ["invested value", "invested amount", "buy value", "buying value", "total investment",
                 "investment value", "cost value", "amount invested", "invested"],
    "sector": ["sector", "industry"],
    "exchange": ["exchange"],
    "currency": ["currency"],
    "type": ["type", "asset type", "asset class"],
    "broker": ["broker", "platform"],
}

# Header names that only appear in mutual-fund exports -> default rows to MF.
MF_HEADER_HINTS = {"scheme name", "fund name", "scheme code", "amfi code", "units", "balance units",
                   "current units", "avg nav", "average nav", "folio", "folio no", "folio number", "amc"}
_FUNDLIKE = re.compile(r"\b(fund|scheme|plan)\b", re.I)

_PAREN = re.compile(r"\([^)]*\)")
_NONWORD = re.compile(r"[^a-z0-9 ]+")


def norm_header(h: object) -> str:
    s = str(h or "").lower()
    s = _PAREN.sub(" ", s).replace("_", " ").replace("-", " ")
    s = _NONWORD.sub(" ", s)
    return " ".join(s.split())


def parse_number(v: object) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("₹", "").replace("$", "").replace("INR", "").strip()
    if s in {"", "-", "--", "NA", "N/A", "na"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---- reading ---------------------------------------------------------------

def read_table(data: bytes, filename: str) -> List[List[str]]:
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")) or data[:2] == b"PK":
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        # Pick the sheet with the most rows that look like a header + data (usually the first).
        best: List[List[str]] = []
        for ws in wb.worksheets:
            rows = [["" if c is None else c for c in r] for r in ws.iter_rows(values_only=True)]
            if _find_header(rows)[0] is not None and len(rows) > len(best):
                best = rows
        return best
    if name.endswith(".xls"):
        raise ValueError("Old .xls files aren't supported — re-save as .xlsx or .csv")
    text = data.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(text), dialect)]


def _map_columns(header: Sequence[object]) -> Dict[str, int]:
    normed = [norm_header(h) for h in header]
    cols: Dict[str, int] = {}
    for role, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normed:
                idx = normed.index(alias)
                if idx not in cols.values():
                    cols[role] = idx
                    break
    return cols


def _find_header(rows: List[List[object]]):
    best_i, best_cols = None, {}
    for i, row in enumerate(rows[:60]):
        cols = _map_columns(row)
        has_id = any(k in cols for k in ("symbol", "isin", "name"))
        if "qty" in cols and has_id and len(cols) > len(best_cols):
            best_i, best_cols = i, cols
    return best_i, best_cols


# ---- resolution ------------------------------------------------------------

def _infer_type(cell_type: str, isin: str, currency: str, default: Optional[str], name: str = "") -> str:
    t = cell_type.strip().upper().replace(" ", "_")
    if t in {"IN_EQ", "US_EQ", "MF", "OTHER"}:
        return t
    if t in {"MUTUAL_FUND", "MUTUALFUND", "FUND"}:
        return "MF"
    if isin.startswith("INF"):
        return "MF"
    if isin.startswith("IN"):
        return "IN_EQ"
    if isin.startswith("US") or currency.upper() == "USD":
        return "US_EQ"
    if default != "US_EQ" and _FUNDLIKE.search(name):
        return "MF"
    return default or "IN_EQ"


def _clean_nse_symbol(s: str) -> str:
    s = s.strip().upper()
    # Kite shows e.g. "IDEA-BE" / "SGBMAR29-GB"; strip series suffixes for lookups.
    return re.sub(r"-(EQ|BE|BZ|SM|ST|GB|N\d|Y\d)$", "", s)


def _cell(row: Sequence[object], cols: Dict[str, int], role: str) -> str:
    i = cols.get(role)
    if i is None or i >= len(row):
        return ""
    v = row[i]
    return "" if v is None else str(v).strip()


def rows_to_holdings(rows: List[List[object]], broker_id: str) -> ImportResult:
    preset = PRESETS.get(broker_id, PRESETS["generic"])
    broker_label = "" if broker_id == "generic" else preset["label"].split(" (")[0]
    hi, cols = _find_header(rows)
    if hi is None:
        raise ValueError(
            "Couldn't find a header row with a quantity column and a symbol/ISIN/name column. "
            "Use the template CSV or check the file."
        )
    default_type = preset["default_type"]
    if MF_HEADER_HINTS & {norm_header(h) for h in rows[hi]}:
        default_type = "MF"
    res = ImportResult(holdings=[], source=f"csv:{broker_id}")
    for n, row in enumerate(rows[hi + 1:], start=hi + 2):
        if not any(str(c).strip() for c in row if c is not None):
            continue
        qty = parse_number(_cell(row, cols, "qty"))
        if not qty or qty <= 0:
            continue  # totals / footer / zero rows
        sym = _cell(row, cols, "symbol")
        name = _cell(row, cols, "name")
        isin = _cell(row, cols, "isin").upper()
        if sym.lower() in {"total", "grand total"} or name.lower() in {"total", "grand total"}:
            continue
        avg = parse_number(_cell(row, cols, "avg"))
        if avg is None:
            inv = parse_number(_cell(row, cols, "invested"))
            avg = (inv / qty) if inv else 0.0
        currency = _cell(row, cols, "currency").upper()
        t = _infer_type(_cell(row, cols, "type"), isin, currency, default_type, name)
        h = Holding(
            type=t, symbol=sym, qty=qty, avg_price=avg or 0.0, name=name, isin=isin,
            exchange=_cell(row, cols, "exchange").upper(), sector=_cell(row, cols, "sector"),
            broker=_cell(row, cols, "broker") or broker_label,
            currency=currency or ("USD" if t == "US_EQ" else "INR"),
        )
        warn = resolve(h)
        if warn:
            res.warnings.append(f"row {n}: {warn}")
        res.holdings.append(h)
    if not res.holdings:
        res.warnings.append("No holdings rows found under the header.")
    return res


def resolve(h: Holding) -> Optional[str]:
    """Fill symbol/name/sector from the master data. Returns a warning string if unresolved."""
    if h.type == "IN_EQ":
        h.exchange = h.exchange if h.exchange in {"NSE", "BSE"} else "NSE"
        eq = None
        if h.symbol:
            h.symbol = _clean_nse_symbol(h.symbol)
            eq = instruments.equity_by_symbol(h.symbol, "NSE")
        if not eq and h.isin:
            eq = instruments.equity_by_isin(h.isin)
        if not eq and not h.symbol and h.name:
            eq = instruments.equity_by_name(h.name)
        if eq:
            h.symbol, h.exchange = eq["symbol"], eq["exchange"]
            h.name = h.name or eq["name"]
            h.isin = h.isin or (eq["isin"] or "")
            h.sector = h.sector or (eq["industry"] or "")
            return None
        if h.symbol:
            return None  # unknown to our master list but may still quote on Yahoo
        h.type, h.symbol = "OTHER", h.name or h.isin
        return f"couldn't match '{h.name or h.isin}' to an NSE symbol — kept as manual asset"
    if h.type == "MF":
        h.sector = h.sector or "Mutual Fund"
        if h.symbol.isdigit():
            return None
        code = mfnav.code_for_isin(h.isin) if h.isin else None
        if not code and h.name:
            hits = instruments.search(h.name, kinds="MF", limit=2)
            if len(hits) == 1:
                code = hits[0]["symbol"]
        if code:
            h.symbol = code
            return None
        h.type, h.symbol = "OTHER", h.name or h.isin
        return f"couldn't match fund '{h.name or h.isin}' — kept as manual asset (CAS import matches by ISIN)"
    if h.type == "US_EQ":
        h.symbol = h.symbol.upper()
        h.currency = "USD"
        if not h.symbol:
            h.type, h.symbol = "OTHER", h.name
            return f"US holding '{h.name}' has no ticker — kept as manual asset"
    if h.type == "OTHER":
        h.symbol = h.symbol or h.name
    return None


def import_file(data: bytes, filename: str, broker_id: str) -> ImportResult:
    return rows_to_holdings(read_table(data, filename), broker_id)
