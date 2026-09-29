from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException

from . import config, db

PBKDF2_ITERATIONS = 200_000

# Ambiguous characters (0/O, 1/I/L) are left out so a code is easy to copy by eye
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def now() -> datetime:
    return datetime.now(timezone.utc)


# --- passwords -------------------------------------------------------------


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
    )
    return hmac.compare_digest(candidate.hex(), digest_hex)


# --- participant codes -----------------------------------------------------


def generate_code(length: int = 6) -> str:
    body = "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))
    return f"{config.CODE_PREFIX}-{body}"


def normalise_code(raw: str) -> str:
    # Accept 'kvt 4f7qh2' or 'KVT-4F7QH2' as the same code.
    cleaned = "".join(ch for ch in raw.upper() if ch.isalnum())
    prefix = config.CODE_PREFIX.upper()
    if cleaned.startswith(prefix):
        cleaned = cleaned[len(prefix):]
    return f"{config.CODE_PREFIX}-{cleaned}"


# --- sessions --------------------------------------------------------------


def create_session(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    issued = now()
    expires = issued + timedelta(hours=config.SESSION_HOURS)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, issued.isoformat(), expires.isoformat()),
    )
    return {"token": token, "expiresAt": expires.isoformat()}


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def purge_expired_sessions(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now().isoformat(),))


# --- FastAPI dependencies --------------------------------------------------
#
# A "dependency" is a function FastAPI runs before running the endpoint. Writing user: dict = Depends(current_user) in an endpoint's arguments means: run this first, give me the result, and if it raises, never run the endpoint.



def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not logged in")
    token = authorization.split(" ", 1)[1].strip()

    with db.connect() as conn:
        row = conn.execute(
            """SELECT u.*, s.token AS session_token, s.expires_at
               FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token = ?""",
            (token,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Session not found")
        if datetime.fromisoformat(row["expires_at"]) < now():
            delete_session(conn, token)
            raise HTTPException(status_code=401, detail="Session expired")
        if not row["active"]:
            raise HTTPException(status_code=403, detail="This account is disabled")
    return dict(row)


def require_admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return user


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    # What we are willing to tell the browser about a user.
    return {
        "id": user["id"],
        "role": user["role"],
        "code": user["code"],
        "username": user["username"],
        "condition": user["condition"],
        "label": user["label"],
    }
