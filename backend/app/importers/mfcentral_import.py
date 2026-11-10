"""MF Central "Detailed CAS" parser (file header `MFCentralDetailCAS_v…`).

casparser (≤1.4.x) only recognises CAMS/KFintech/NSDL/CDSL watermarks, so MF Central statements
fail there with "Could not identify the CAS issuer". Layout, per scheme:

    FOLIO NO: 1234567890
    <Scheme name> (Advisor: INZ000031633/ZERODHA BROKING LIMITED ISIN: INF… Opening Unit Balance: 1,234.567
    DD-MON-YYYY <description> <amount> <units> <price> <unit balance>     (redemptions: (amount) (units))
    …
    Closing Unit Balance: 1,234.567 Nav as on DD-MON-YYYY: INR 12.3456 Valuation on DD-Mon-YYYY : INR 12,345.67

There is no cost-value field, so cost is rebuilt FIFO from the transactions. Units in the opening
balance have unknown cost (the statement period often starts on 1 April). Then avg_price = 0 and a
warning asks for a "since inception" statement. The UI treats avg 0 as "cost unknown".

Privacy: the text includes name, PAN, email and address. Nothing here logs or stores it.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from ..models import Holding, ImportResult
from ..prices import mfnav

MARKER = "MFCentralDetailCAS"

_NUM = r"\(?-?[\d,]*\.?\d+\)?"
HEADER_RE = re.compile(
    r"^(?P<name>.+?)\s*\(Advisor:\s*(?P<advisor>.*?)\s+ISIN:\s*(?P<isin>INF[0-9A-Z]{9})"
    r"\s+Opening Unit Balance:\s*(?P<open>" + _NUM + ")"
)
# pypdfium2 can put the opening-balance column on a later line, often after
# the printed KYC line. Keep the header fields separate so both layouts work.
HEADER_BASE_RE = re.compile(
    r"^(?P<name>.+?)\s*\(Advisor:\s*(?P<advisor>.*?)\s+ISIN:\s*(?P<isin>INF[0-9A-Z]{9})\s*$"
)
OPEN_RE = re.compile(r"^Opening Unit Balance:\s*(?P<open>" + _NUM + r")\s*$")
TXN_RE = re.compile(
    r"^(?P<date>\d{2}-[A-Za-z]{3}-\d{4})\s+(?P<desc>.*?)\s+(?P<amount>" + _NUM + r")\s+(?P<units>" + _NUM + r")"
    r"\s+(?P<price>" + _NUM + r")\s+(?P<balance>" + _NUM + r")\s*$"
)
CLOSE_RE = re.compile(
    r"Closing Unit Balance:\s*(?P<units>" + _NUM + r")\s+Nav as on\s+(?P<navdate>\S+?):\s*INR\s*(?P<nav>" + _NUM + ")"
    r"(?:.*?Valuation on .*?INR\s*(?P<value>" + _NUM + "))?"
)

# Distributor (advisor) → platform label. Registration codes were observed paired with these names
# in real statements; names are matched as keywords. Unknown → "MF (CAS)".
ADVISOR_CODES = {"INZ000031633": "Zerodha", "INZ000208032": "Groww"}
ADVISOR_NAMES = [
    ("ZERODHA", "Zerodha"), ("NEXTBILLION", "Groww"), ("GROWW", "Groww"), ("UPSTOX", "Upstox"),
    ("RKSV", "Upstox"), ("INDMONEY", "INDmoney"), ("KUVERA", "Kuvera"), ("PAYTM", "Paytm Money"),
    ("ET MONEY", "ET Money"),
]


def num(s: str) -> float:
    s = s.strip().replace(",", "")
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()"))
    return -abs(v) if neg else v


def platform(advisor: str) -> str:
    code, _, name = advisor.partition("/")
    up = name.upper()
    for kw, label in ADVISOR_NAMES:
        if kw in up:
            return label
    if code.strip() in ADVISOR_CODES:
        return ADVISOR_CODES[code.strip()]
    return "MF (CAS)"


class _Scheme:
    def __init__(self, name: str, isin: str, advisor: str, opening: float) -> None:
        self.name, self.isin, self.advisor = name, isin, advisor
        # FIFO lots: [units, cost or None (unknown)]
        self.lots: List[List[Optional[float]]] = [[opening, None]] if opening > 0 else []
        self.closing: Optional[float] = None
        self.nav: Optional[float] = None

    def buy(self, units: float, amount: float) -> None:
        self.lots.append([units, abs(amount)])

    def sell(self, units: float) -> None:
        left = units
        while left > 1e-9 and self.lots:
            lot = self.lots[0]
            take = min(lot[0], left)
            if lot[1] is not None:
                lot[1] -= lot[1] * (take / lot[0])
            lot[0] -= take
            left -= take
            if lot[0] <= 1e-9:
                self.lots.pop(0)

    def cost(self) -> Tuple[Optional[float], float]:
        """(total cost of remaining units or None if any remaining lot is unknown, remaining units)."""
        units = sum(l[0] for l in self.lots)
        if any(l[1] is None and l[0] > 1e-6 for l in self.lots):
            return None, units
        return sum(l[1] for l in self.lots), units


def is_mfcentral(text: str) -> bool:
    return MARKER in text[:5000]


def parse_text(text: str) -> ImportResult:
    res = ImportResult(holdings=[], source="cas")
    schemes: List[_Scheme] = []
    cur: Optional[_Scheme] = None
    pending_header = None
    lines = [" ".join(r.split()) for r in text.splitlines()]
    lines = [l for l in lines if l]
    for i, line in enumerate(lines):
        m = HEADER_RE.match(line)
        if not m and "ISIN:" in line and "Opening Unit Balance" in line and i > 0:
            # long scheme names can wrap onto the previous line
            m = HEADER_RE.match(lines[i - 1] + " " + line)
        if m:
            cur = _Scheme(m["name"].strip(), m["isin"], m["advisor"], num(m["open"]))
            pending_header = None
            schemes.append(cur)
            continue

        base = HEADER_BASE_RE.match(line)
        if base:
            # Some MF Central PDFs render the opening-balance column separately
            # from the scheme header (with `KYC : OK` between the two lines).
            pending_header = base
            continue

        if pending_header:
            opening = OPEN_RE.match(line)
            if opening:
                cur = _Scheme(
                    pending_header["name"].strip(),
                    pending_header["isin"],
                    pending_header["advisor"],
                    num(opening["open"]),
                )
                schemes.append(cur)
                pending_header = None
                continue

        if cur is None:
            continue
        m = CLOSE_RE.search(line)
        if m:
            cur.closing, cur.nav = num(m["units"]), num(m["nav"])
            cur = None
            continue
        m = TXN_RE.match(line)
        if m:
            units, amount = num(m["units"]), num(m["amount"])
            if units > 0:
                cur.buy(units, amount)
            elif units < 0:
                cur.sell(-units)

    period = re.search(r"From Date\s*:\s*(\S+)\s+To Date\s*:\s*(\S+)", text)
    unknown_cost = []
    merged: Dict[Tuple[str, str], Holding] = {}
    for s in schemes:
        if not s.closing or s.closing <= 0:
            continue
        cost, fifo_units = s.cost()
        if abs(fifo_units - s.closing) > max(0.01, 0.001 * s.closing):
            # Parsing missed some transactions (e.g. a wrapped line); don't trust FIFO cost.
            cost = None
        code = mfnav.code_for_isin(s.isin)
        broker = platform(s.advisor)
        key = (code or s.isin, broker)
        if key in merged:  # same scheme, same platform, different folio
            h = merged[key]
            if cost is None or h.avg_price == 0:
                h.avg_price, cost = 0.0, None
            else:
                h.avg_price = (h.avg_price * h.qty + cost) / (h.qty + s.closing)
            h.qty += s.closing
        else:
            h = Holding(
                type="MF" if code else "OTHER",
                symbol=code or s.name,
                qty=s.closing,
                avg_price=(cost / s.closing) if cost is not None else 0.0,
                name=s.name,
                isin=s.isin,
                broker=broker,
                sector="Mutual Fund",
            )
            if not code:
                h.price_override = s.nav
                res.warnings.append(f"'{s.name}': ISIN not found in the AMFI list, kept as a manual asset at the CAS NAV")
            merged[key] = h
        if cost is None:
            unknown_cost.append(s.name)

    res.holdings = list(merged.values())
    if unknown_cost:
        since = f" (this one starts {period.group(1)})" if period else ""
        res.warnings.append(
            f"Cost basis unknown for {len(unknown_cost)} fund(s), because they hold units bought before the statement "
            f"period{since}. Their total % will show as '—'. Fix: download the MF Central CAS with the period set "
            "to 'since inception', or edit the avg price by hand. Affected: " + "; ".join(unknown_cost[:8])
            + ("…" if len(unknown_cost) > 8 else "")
        )
    if not res.holdings:
        res.warnings.append("No funds with a closing balance > 0 found in this MF Central statement.")
    return res
