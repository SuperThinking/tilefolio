from __future__ import annotations

import os

os.environ.setdefault("TF_LOAD_INSTRUMENTS", "0")
os.environ.setdefault("TF_SESSION_SECRET", "test-secret")

import asyncio

import httpx
import pytest

from app import db, http
from app.prices import fx, service


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    db.set_db_path(tmp_path / "test.sqlite3")
    service.cache.clear()
    fx._cache.update(rate=None, ts=0.0, source=None)
    yield


@pytest.fixture
def seed_master():
    with db.connect() as c:
        c.executemany(
            "INSERT INTO equities(symbol, exchange, name, isin, industry) VALUES(?,?,?,?,?)",
            [
                ("RELIANCE", "NSE", "Reliance Industries Limited", "INE002A01018", "Oil Gas & Consumable Fuels"),
                ("INFY", "NSE", "Infosys Limited", "INE009A01021", "Information Technology"),
                ("TCS", "NSE", "Tata Consultancy Services Limited", "INE467B01029", "Information Technology"),
            ],
        )
        c.executemany(
            "INSERT INTO mf_schemes(code, name, isin_growth, isin_reinv) VALUES(?,?,?,?)",
            [
                ("120503", "Axis ELSS Tax Saver Fund - Direct Plan - Growth", "INF846K01EW2", None),
                ("122639", "Parag Parikh Flexi Cap Fund - Direct Plan - Growth", "INF879O01027", None),
            ],
        )


class Router:
    """Tiny URL-substring -> handler router for httpx.MockTransport."""

    def __init__(self):
        self.routes = []
        self.calls = []

    def add(self, needle, handler):
        self.routes.append((needle, handler))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        url = str(request.url)
        for needle, handler in self.routes:
            if needle in url:
                return handler(request) if callable(handler) else handler
        return httpx.Response(404, json={"error": "no mock for " + url})


@pytest.fixture
def mock_http():
    router = Router()
    http.set_client(httpx.AsyncClient(transport=httpx.MockTransport(router)))
    yield router
    http._client = None


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def reset_backoff():
    from app.prices import finnhub, yahoo

    yahoo.backoff.until = 0
    finnhub.backoff.until = 0
    yield
