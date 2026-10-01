
from __future__ import annotations

import sqlite3

from . import config

DB_PATH = config.DB_PATH
DATA_DIR = DB_PATH.parent

SCHEMA = """
-- One row per person who can log in: students (identified by a printed code) and admins (username + password)
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    role          TEXT NOT NULL CHECK (role IN ('student', 'admin')),
    code          TEXT UNIQUE,      -- students
    username      TEXT UNIQUE,      -- admins
    password_hash TEXT,             -- admins
    condition     TEXT,             -- students: 'intervention' | 'control' | NULL
    label         TEXT,             -- free note, e.g. "pilot 2, group B"
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

-- A login session. The token is a random string the browser sends back on every request
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS submissions (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES users(id),
    lesson_id      TEXT NOT NULL,
    lesson_type    TEXT NOT NULL,
    lesson_version INTEGER,         -- the version field in the lesson file
    lesson_hash    TEXT,            -- hash of the file as it was at submit time
    attempt_no     INTEGER NOT NULL,
    payload_json   TEXT NOT NULL,   -- {"code": "..."} or {"placements": {...}}
    started_at     TEXT,
    submitted_at   TEXT NOT NULL,
    duration_ms    INTEGER
);

CREATE TABLE IF NOT EXISTS self_assessments (
    id            TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL REFERENCES submissions(id),
    confidence    INTEGER NOT NULL,  -- 1..5
    notes         TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id            TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL REFERENCES submissions(id),
    source        TEXT NOT NULL,     -- 'placeholder' now, 'llm' later
    body_json     TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT,
    lesson_id    TEXT,
    type         TEXT NOT NULL,      -- 'lesson_opened', 'hint_opened', ...
    payload_json TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_submissions_user
    ON submissions(user_id, lesson_id);
CREATE INDEX IF NOT EXISTS idx_events_user
    ON events(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user
    ON sessions(user_id);
"""


def connect() -> sqlite3.Connection:
    # Open a connection. row_factory lets us read columns by name.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
