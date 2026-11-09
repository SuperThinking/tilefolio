"""Broker presets for guided CSV/XLSX import.

Each preset adds header aliases and defaults to the generic parser in csv_import.py, plus the
"how to export" steps shown in the UI. Export paths in broker UIs change often, so the UI says
the steps are approximate. Add a broker by appending to PRESETS; no parser changes needed if
its headers map onto the generic aliases.

`connect` lists the user-supplied-key (bring-your-own-key) sync flows available for that broker.
"""
from __future__ import annotations

PRESETS = {
    "zerodha": {
        "label": "Zerodha",
        "default_type": "IN_EQ",
        "connect": ["kite"],
        "steps": [
            "Open console.zerodha.com → Portfolio → Holdings.",
            "Click the download icon and choose XLSX or CSV.",
            "Alternatively on kite.zerodha.com → Holdings → Download (CSV).",
            "Drop the file here.",
        ],
    },
    "groww": {
        "label": "Groww",
        "default_type": "IN_EQ",
        "connect": [],
        "steps": [
            "Open groww.in → Profile → Reports (or Stocks → Holdings).",
            "Download the 'Holdings' statement for stocks (XLSX).",
            "For mutual funds, prefer the CAS PDF import (covers all platforms).",
            "Drop the file here.",
        ],
    },
    "upstox": {
        "label": "Upstox",
        "default_type": "IN_EQ",
        "connect": ["upstox"],
        "steps": [
            "Open the Upstox web app → Reports → Holdings.",
            "Download the holdings report (CSV/XLSX).",
            "Drop the file here.",
        ],
    },
    "indmoney": {
        "label": "INDmoney (US stocks)",
        "default_type": "US_EQ",
        "connect": [],
        "steps": [
            "In INDmoney, open US Stocks → Portfolio and export/download holdings if available.",
            "If no export exists, use the generic template and fill ticker, quantity, avg price (USD).",
            "Drop the file here.",
        ],
    },
    "generic": {
        "label": "Other / template",
        "default_type": None,
        "connect": [],
        "steps": [
            "Download the template CSV below and fill one row per holding.",
            "type = IN_EQ (Indian stock), US_EQ (US stock), MF (AMFI scheme code), OTHER (manual).",
            "Any CSV/XLSX with columns like Symbol/ISIN, Quantity and Average Price also works.",
        ],
    },
}

TEMPLATE_CSV = (
    "type,symbol,exchange,name,qty,avg_price,currency,sector,broker\n"
    "IN_EQ,RELIANCE,NSE,Reliance Industries,10,2450.50,INR,,Zerodha\n"
    "US_EQ,AAPL,,Apple Inc,5,175.20,USD,Technology,INDmoney\n"
    "MF,119551,,,120.345,52.10,INR,,CAMS\n"
    "OTHER,Gold coin,,24K gold 10g,1,60000,INR,Gold,\n"
)


def public_presets() -> list:
    return [
        {"id": k, "label": v["label"], "steps": v["steps"], "connect": v["connect"]}
        for k, v in PRESETS.items()
    ]
