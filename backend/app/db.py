"""Tiny SQLite layer (stdlib only). One short-lived connection per unit of work."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    google_sub  TEXT UNIQUE NOT NULL,
    email       TEXT,
    name        TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Local-first sync: the browser is the source of truth; this is the signed-in backup.
CREATE TABLE IF NOT EXISTS user_state (
    user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    state_json  TEXT NOT NULL,
    updated_at  INTEGER NOT NULL           -- client-supplied epoch ms (last-write-wins)
);

-- Daily AMFI NAV snapshots so we can compute MF day change (NAVAll.txt has no prev NAV).
CREATE TABLE IF NOT EXISTS nav_history (
    code      TEXT NOT NULL,
    nav_date  TEXT NOT NULL,               -- ISO yyyy-mm-dd
    nav       REAL NOT NULL,
    PRIMARY KEY (code, nav_date)
);

CREATE TABLE IF NOT EXISTS mf_schemes (
    code        TEXT PRIMARY KEY,          -- AMFI scheme code (same as mfapi.in)
    name        TEXT NOT NULL,
    isin_growth TEXT,
    isin_reinv  TEXT
);
CREATE INDEX IF NOT EXISTS ix_mf_isin_g ON mf_schemes(isin_growth);
CREATE INDEX IF NOT EXISTS ix_mf_isin_r ON mf_schemes(isin_reinv);

CREATE TABLE IF NOT EXISTS equities (
    symbol    TEXT NOT NULL,
    exchange  TEXT NOT NULL,               -- NSE (BSE later)
    name      TEXT NOT NULL,
    isin      TEXT,
    industry  TEXT,
    PRIMARY KEY (exchange, symbol)
);
CREATE INDEX IF NOT EXISTS ix_eq_isin ON equities(isin);

CREATE TABLE IF NOT EXISTS broker_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    broker      TEXT NOT NULL,
    note        TEXT,
    user_id     INTEGER,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meta (
    key    TEXT PRIMARY KEY,
    value  TEXT
);
"""

_db_path: Path = settings.db_path


def set_db_path(path: Path) -> None:
    """Used by tests to point at a temp database."""
    global _db_path
    _db_path = path
    init_db()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(_db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(SCHEMA)


def get_meta(key: str) -> Optional[str]:
    with connect() as c:
        row = c.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
