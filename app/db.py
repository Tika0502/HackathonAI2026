"""Database helpers. Everything is stored in one SQLite file: rota.db"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "rota.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    pin TEXT NOT NULL,
    is_manager INTEGER NOT NULL DEFAULT 0,
    is_demo INTEGER NOT NULL DEFAULT 0      -- 1 = a real person uses this login in the demo (never auto-answered)
);

CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,                     -- 2026-11-21
    name TEXT NOT NULL,                     -- Morning / Evening
    start TEXT NOT NULL,                    -- 14:00
    end TEXT NOT NULL,                      -- 22:00
    needed INTEGER NOT NULL
);

-- The rota: who works which shift
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY,
    shift_id INTEGER NOT NULL,
    worker_id INTEGER NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'working', -- working / sick / removed (manager needed fewer people)
    is_replacement INTEGER NOT NULL DEFAULT 0  -- 1 = covered a sick colleague
);

-- Spots the agent must fill
CREATE TABLE IF NOT EXISTS open_spots (
    id INTEGER PRIMARY KEY,
    shift_id INTEGER NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    reason TEXT NOT NULL,                   -- plan / sick / surge
    status TEXT NOT NULL DEFAULT 'open',    -- open / filled / unfilled / cancelled
    filled_by INTEGER,
    created_at TEXT NOT NULL
);

-- Every invitation and its answer
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY,
    spot_id INTEGER NOT NULL,
    worker_id INTEGER NOT NULL,
    wave INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'waiting', -- waiting / yes / no / timeout / cancelled / too_late
    sent_at TEXT NOT NULL,
    answered_at TEXT
);

-- The agent's reasons and messages for the manager
CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY,
    time TEXT NOT NULL,
    spot_id INTEGER,
    kind TEXT NOT NULL DEFAULT 'agent',     -- agent / system / manager (manager = alert for the manager)
    text TEXT NOT NULL
);

-- Worked shifts, used for monthly pay (sick = 0 hours)
CREATE TABLE IF NOT EXISTS shift_records (
    id INTEGER PRIMARY KEY,
    worker_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    hours REAL NOT NULL,
    is_replacement INTEGER NOT NULL DEFAULT 0,
    is_sick INTEGER NOT NULL DEFAULT 0
);

-- One-time messages to a worker (e.g. "your shift was cancelled")
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    worker_id INTEGER NOT NULL,
    time TEXT NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "hourly_rate": "2500",            # one rate for everyone
    "currency": "HUF",
    "offer_timeout_minutes": "3",     # how long a worker has to answer: 3 (default) or 5
    "demo_speed": "1",                # 1 = real time. 10 = everything 10x faster (for the demo)
    "use_ai": "1",                    # 1 = OpenAI agent decides, 0 = plain-code rules
    "bots_on": "1",                   # 1 = fake workers answer offers by themselves
}


def connect():
    """Open a new connection. Rows behave like dicts: row["name"]."""
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))


def query(sql, params=()):
    """Run a SELECT and return a list of dicts."""
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE. Returns the new row id (for INSERT)."""
    with connect() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid


def get_setting(key):
    row = query_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else DEFAULT_SETTINGS.get(key)


def set_setting(key, value):
    execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, str(value)))
