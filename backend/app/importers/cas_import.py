"""CAMS / KFintech Consolidated Account Statement (CAS) PDF import via `casparser` (MIT).

Privacy: the PDF contains PAN, address and folio numbers. We parse it in memory, never write
it to disk, never log its contents, and return only scheme-level holdings.
"""
from __future__ import annotations

import io
from typing import Any, Dict

from ..models import Holding, ImportResult
from ..prices import mfnav


def _g(obj: Any, key: str, default=None):
    """casparser returns dicts in some versions and pydantic/dataclass objects in others."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def pdf_text(data: bytes, password: str) -> str:
    """Extract text with pypdfium2 (a casparser dependency). Raises ValueError on bad password."""
    import pypdfium2 as pdfium

    try:
        doc = pdfium.PdfDocument(data, password=password or None)
    except pdfium.PdfiumError as e:
        if "password" in str(e).lower():
            raise ValueError("Wrong PDF password. It's usually your PAN in capitals, or the one you set when requesting the CAS.")
        raise ValueError("Couldn't open this PDF.") from None
    try:
        out = []
        for i in range(len(doc)):
            page = doc[i]
            tp = page.get_textpage()
            out.append(tp.get_text_range())
            tp.close()
            page.close()
        return "\n".join(out)
    finally:
        doc.close()


def import_cas(data: bytes, password: str) -> ImportResult:
    try:
        import casparser  # heavy import; keep lazy
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("casparser is not installed on the server") from e

    text = pdf_text(data, password)
    from . import mfcentral_import

    if mfcentral_import.is_mfcentral(text):
        return mfcentral_import.parse_text(text)

    try:
        parsed = casparser.read_cas_pdf(io.BytesIO(data), password)
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "decrypt" in msg:
            raise ValueError("Wrong PDF password. It's usually your PAN in capitals, or the one you set when requesting the CAS.")
        if "issuer" in msg:
            raise ValueError(
                "Unrecognised statement. Supported: CAMS/KFintech CAS and MF Central detailed CAS."
            )
        raise ValueError("Couldn't parse this PDF as a CAS statement.") from None
    if type(parsed).__name__ == "NSDLCASData" or _g(parsed, "accounts", None) is not None:
        raise ValueError("NSDL/CDSL depository CAS isn't supported yet. Use a CAMS/KFintech or MF Central CAS.")

    res = ImportResult(holdings=[], source="cas")
    merged: Dict[str, Holding] = {}
    for folio in _g(parsed, "folios", []) or []:
        amc = _g(folio, "amc", "") or ""
        for s in _g(folio, "schemes", []) or []:
            units = float(_g(s, "close", 0) or 0)
            if units <= 0:
                continue
            isin = (_g(s, "isin", "") or "").upper()
            code = str(_g(s, "amfi", "") or "") or (mfnav.code_for_isin(isin) if isin else None)
            val = _g(s, "valuation", {}) or {}
            cost = _g(val, "cost", None)
            name = _g(s, "scheme", "") or ""
            key = code or isin or name
            if key in merged:  # same scheme across folios -> sum units, weight cost
                h = merged[key]
                total_cost = h.avg_price * h.qty + (float(cost) if cost else 0.0)
                h.qty += units
                h.avg_price = total_cost / h.qty if h.qty else 0.0
                continue
            h = Holding(
                type="MF" if code else "OTHER",
                symbol=code or name,
                qty=units,
                avg_price=(float(cost) / units) if cost else 0.0,
                name=name,
                isin=isin,
                broker=amc.replace(" Mutual Fund", "") if amc else "CAS",
                sector="Mutual Fund",
            )
            if not code:
                nav = _g(val, "nav", None)
                h.price_override = float(nav) if nav else None
                res.warnings.append(f"'{name}': no AMFI code found — kept as manual asset at CAS NAV")
            if not cost:
                res.warnings.append(f"'{name}': CAS has no cost basis (summary CAS?) — avg price set to 0")
            merged[key] = h
    res.holdings = list(merged.values())
    if not res.holdings:
        res.warnings.append("No mutual fund holdings with units > 0 found in this CAS.")
    return res
