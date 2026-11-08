
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
    condition     TEXT,             -- students: 'restricted' | 'unrestricted' | NULL (NULL behaves as unrestricted)
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

CREATE TABLE IF NOT EXISTS evaluations (
    id             TEXT PRIMARY KEY,
    submission_id  TEXT NOT NULL REFERENCES submissions(id),
    grader_version TEXT NOT NULL,
    status         TEXT NOT NULL,
    solved         INTEGER,
    result_json    TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id             TEXT PRIMARY KEY,
    submission_id  TEXT REFERENCES submissions(id),
    purpose        TEXT NOT NULL,     -- 'feedback' | 'chat'
    attempt        INTEGER NOT NULL,  -- 1, or 2 for the retry
    model          TEXT,
    prompt_version TEXT,
    messages_json  TEXT NOT NULL,     -- exactly what was sent
    response       TEXT,              -- exactly what came back
    outcome        TEXT NOT NULL,     -- ok | invalid_json | invalid_shape | leak | code_block | not_danish | error
    detail         TEXT,
    latency_ms     INTEGER,
    created_at     TEXT NOT NULL
);


-- One conversation per attempt at a task. Created when feedback is first produced (restricted) or,
-- later, when the student first opens the chat (unrestricted). Linked to the submission once there is one.
CREATE TABLE IF NOT EXISTS conversations (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id),
    lesson_id     TEXT NOT NULL,
    condition     TEXT NOT NULL,     -- the condition in force when it started: 'restricted' | 'unrestricted'
    submission_id TEXT REFERENCES submissions(id),
    created_at    TEXT NOT NULL,
    closed_at     TEXT               -- set when a newer attempt at the same lesson starts; no more replies after that
);

-- Everything shown in the conversation box, in order.
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    seq             INTEGER NOT NULL,  -- 1, 2, 3 ... within the conversation
    role            TEXT NOT NULL CHECK (role IN ('student', 'assistant')),
    kind            TEXT NOT NULL,     -- 'chat' | 'self_assessment' | 'feedback' | 'fallback'
    body_json       TEXT NOT NULL,     -- {"text": ...}, or the feedback object, or {"confidence", "notes"}
    submission_id   TEXT REFERENCES submissions(id),
    counted         INTEGER NOT NULL DEFAULT 0,  -- 1 if this student message counts towards the cap
    created_at      TEXT NOT NULL
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
CREATE INDEX IF NOT EXISTS idx_llm_calls_submission
    ON llm_calls(submission_id, created_at);
CREATE INDEX IF NOT EXISTS idx_evaluations_submission
    ON evaluations(submission_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_user
    ON conversations(user_id, lesson_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, seq);
"""


def connect() -> sqlite3.Connection:
    # Open a connection. row_factory lets us read columns by name.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate(conn: sqlite3.Connection) -> None:
    """Bring a database made by an older version of the code up to date.

    CREATE TABLE IF NOT EXISTS adds new tables, but never changes a table that
    already exists - so new columns on old tables are added here. Every step
    checks first, so running this again on an up-to-date database does nothing.
    """
    # Nov 2026: chat. Model calls can belong to a conversation, not only a submission.
    if "conversation_id" not in _columns(conn, "llm_calls"):
        conn.execute("ALTER TABLE llm_calls ADD COLUMN conversation_id TEXT REFERENCES conversations(id)")
    # Nov 2026: conditions renamed to say what they mean.
    conn.execute("UPDATE users SET condition = 'restricted' WHERE condition = 'intervention'")
    conn.execute("UPDATE users SET condition = 'unrestricted' WHERE condition = 'control'")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        migrate(conn)
