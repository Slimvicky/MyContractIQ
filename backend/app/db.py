"""SQLite storage: users, sessions, contracts, rate checks, portfolio reviews."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    business_name TEXT NOT NULL,
    business_type TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    counterparty TEXT NOT NULL,
    line_type TEXT NOT NULL CHECK (line_type IN ('expense', 'revenue')),
    category TEXT NOT NULL DEFAULT 'Other',
    annual_value REAL NOT NULL DEFAULT 0,
    start_date TEXT,
    end_date TEXT,
    notice_days INTEGER NOT NULL DEFAULT 30,
    auto_renew INTEGER NOT NULL DEFAULT 0,
    owner TEXT DEFAULT '',
    scope TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    file_name TEXT,
    file_path TEXT,
    needs_review INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rate_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    source TEXT NOT NULL,
    trigger TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS portfolio_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # migrations for databases created before these columns existed
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        if "calendar_pref" not in cols:
            # 'unset' = not asked yet, 'all' = subscribed to all contracts, 'none' = declined
            conn.execute("ALTER TABLE users ADD COLUMN calendar_pref TEXT NOT NULL DEFAULT 'unset'")
        if "calendar_feed_hash" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN calendar_feed_hash TEXT")
