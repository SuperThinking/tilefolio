"""Core domain types shared by importers, brokers and the price service.

Instrument key format (used everywhere — frontend, cache, quotes API):
    IN_EQ:<EXCHANGE>:<SYMBOL>   e.g. IN_EQ:NSE:RELIANCE
    US_EQ:<SYMBOL>              e.g. US_EQ:AAPL
    MF:<AMFI_CODE>              e.g. MF:119551
    OTHER:<id>                  manual asset, no live price
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import List, Optional

ASSET_TYPES = ("IN_EQ", "US_EQ", "MF", "OTHER")


@dataclass
class Instrument:
    type: str
    symbol: str
    exchange: str = ""

    @property
    def key(self) -> str:
        if self.type == "IN_EQ":
            return f"IN_EQ:{self.exchange or 'NSE'}:{self.symbol}"
        return f"{self.type}:{self.symbol}"

    @classmethod
    def parse(cls, key: str) -> "Instrument":
        parts = key.split(":")
        if not parts or parts[0] not in ASSET_TYPES:
            raise ValueError(f"bad instrument key: {key!r}")
        if parts[0] == "IN_EQ":
            if len(parts) != 3 or not parts[2]:
                raise ValueError(f"bad instrument key: {key!r}")
            return cls("IN_EQ", parts[2].upper(), parts[1].upper())
        if len(parts) != 2 or not parts[1]:
            raise ValueError(f"bad instrument key: {key!r}")
        sym = parts[1] if parts[0] == "MF" else parts[1].upper()
        return cls(parts[0], sym)


@dataclass
class Holding:
    """Normalised holding produced by every importer. Mirrors the frontend Holding shape."""

    type: str                         # IN_EQ | US_EQ | MF | OTHER
    symbol: str                       # NSE symbol, US ticker, AMFI code, or free text
    qty: float
    avg_price: float
    name: str = ""
    exchange: str = ""                # NSE/BSE for IN_EQ
    currency: str = "INR"
    broker: str = ""
    sector: str = ""
    isin: str = ""
    price_override: Optional[float] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def key(self) -> str:
        if self.type == "OTHER":
            return f"OTHER:{self.id}"
        return Instrument(self.type, self.symbol, self.exchange).key

    def to_dict(self) -> dict:
        d = asdict(self)
        d["key"] = self.key
        # camelCase for the JS client
        d["avgPrice"] = d.pop("avg_price")
        d["priceOverride"] = d.pop("price_override")
        return d


@dataclass
class Quote:
    key: str
    price: float
    prev_close: Optional[float]
    currency: str
    source: str
    ts: float                          # epoch seconds when fetched
    as_of: Optional[str] = None        # provider timestamp / NAV date

    @property
    def change_pct(self) -> Optional[float]:
        if not self.prev_close:
            return None
        return (self.price - self.prev_close) / self.prev_close * 100.0

    def to_dict(self) -> dict:
        return {
            "price": self.price,
            "prevClose": self.prev_close,
            "changePct": self.change_pct,
            "currency": self.currency,
            "source": self.source,
            "ts": self.ts,
            "asOf": self.as_of,
        }


@dataclass
class ImportResult:
    holdings: List[Holding]
    warnings: List[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "holdings": [h.to_dict() for h in self.holdings],
            "warnings": self.warnings,
        }
