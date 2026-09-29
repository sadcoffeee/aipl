from __future__ import annotations

import getpass
import sys
import uuid
from datetime import datetime, timezone

from . import auth, db


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    username = sys.argv[1]

    password = getpass.getpass("Password: ")
    if len(password) < 8:
        print("Use at least 8 characters.")
        return 1
    if password != getpass.getpass("Repeat password: "):
        print("Passwords did not match.")
        return 1

    db.init_db()
    with db.connect() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET password_hash = ?, active = 1 WHERE id = ?",
                (auth.hash_password(password), existing["id"]),
            )
            print(f"Password reset for admin '{username}'.")
        else:
            conn.execute(
                """INSERT INTO users (id, role, username, password_hash, active, created_at)
                   VALUES (?, 'admin', ?, ?, 1, ?)""",
                (
                    f"u_{uuid.uuid4().hex[:12]}",
                    username,
                    auth.hash_password(password),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            print(f"Admin '{username}' created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
