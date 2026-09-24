"""
SQLite storage layer.

Deliberately not an ORM: SQLite + hand-written, parameterized SQL keeps the
dependency tree (and RAM footprint) small, per the PRD's 8GB-RAM constraint,
and every query below uses `?` placeholders — never string formatting — so
there's no SQL injection surface even though most inputs originate from
LLM output or email content that we don't fully trust.
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import get_settings

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source_email_id TEXT NOT NULL,
    subject TEXT,
    sender TEXT,
    snippet TEXT,
    task_type TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    confidence REAL,
    latency_ms REAL,
    cost_estimate REAL,
    error_reason TEXT
);

CREATE TABLE IF NOT EXISTS run_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    step_name TEXT NOT NULL,   -- perceive | plan | act | reflect | escalate
    detail TEXT,               -- JSON blob: the reasoning trace
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    input TEXT,
    output TEXT,
    status TEXT NOT NULL DEFAULT 'proposed',  -- proposed|approved|rejected|completed
    created_at TEXT NOT NULL,
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS tracking_sheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sender TEXT,
    subject TEXT,
    task_type TEXT,
    key_dates TEXT,
    amount TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL UNIQUE,
    encrypted_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_emails (
    email_id TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_actions_run ON actions(run_id);
CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
"""


def get_connection() -> sqlite3.Connection:
    """One connection per thread (SQLite connections aren't thread-safe)."""
    if not hasattr(_local, "conn"):
        settings = get_settings()
        conn = sqlite3.connect(settings.database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _local.conn = conn
    return _local.conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def tx():
    """Simple transaction context manager."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def from_json(value: str | None):
    if not value:
        return None
    return json.loads(value)
