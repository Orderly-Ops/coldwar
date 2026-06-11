"""SQLite-backed storage: OAuth tokens, decisions, feedback, per-account checkpoints.

Deliberately boring. One file, one connection-per-call, no ORM. The schema is
created on first use so self-hosting is "just run it".
"""

import json
import sqlite3
import time
from contextlib import contextmanager

from coldwar.models import Message

SCHEMA = """
CREATE TABLE IF NOT EXISTS tokens (
    account     TEXT PRIMARY KEY,
    provider    TEXT NOT NULL,
    data        TEXT NOT NULL,            -- JSON: access/refresh tokens + expiry
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    account     TEXT PRIMARY KEY,
    since       REAL NOT NULL             -- fetch_new(since=...) high-water mark
);

CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account     TEXT NOT NULL,
    message_id  TEXT NOT NULL,
    sender      TEXT,
    subject     TEXT,
    is_cold     INTEGER NOT NULL,
    score       REAL NOT NULL,
    reasons     TEXT NOT NULL,            -- JSON list[str]
    fingerprint TEXT,
    created_at  REAL NOT NULL,
    UNIQUE(account, message_id)
);

CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account     TEXT NOT NULL,
    message_id  TEXT NOT NULL,
    is_cold     INTEGER NOT NULL,         -- user-supplied truth (0 = "not cold")
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS senders (
    account     TEXT NOT NULL,
    sender      TEXT NOT NULL,            -- lets us answer "first contact?"
    first_seen  REAL NOT NULL,
    PRIMARY KEY (account, sender)
);
"""


class Storage:
    def __init__(self, path: str = "coldwar.db"):
        self.path = path
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- OAuth tokens -----------------------------------------------------

    def save_tokens(self, account: str, provider: str, data: dict) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO tokens(account, provider, data, updated_at) "
                "VALUES(?,?,?,?) ON CONFLICT(account) DO UPDATE SET "
                "provider=excluded.provider, data=excluded.data, "
                "updated_at=excluded.updated_at",
                (account, provider, json.dumps(data), time.time()),
            )

    def load_tokens(self, account: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT data FROM tokens WHERE account=?", (account,)
            ).fetchone()
        return json.loads(row["data"]) if row else None

    # --- Checkpoints ------------------------------------------------------

    def checkpoint(self, account: str) -> float:
        with self._conn() as c:
            row = c.execute(
                "SELECT since FROM checkpoints WHERE account=?", (account,)
            ).fetchone()
        return row["since"] if row else 0.0

    def advance_checkpoint(self, account: str, since: float | None = None) -> None:
        since = time.time() if since is None else since
        with self._conn() as c:
            c.execute(
                "INSERT INTO checkpoints(account, since) VALUES(?,?) "
                "ON CONFLICT(account) DO UPDATE SET since=excluded.since",
                (account, since),
            )

    # --- First-contact tracking ------------------------------------------

    def is_first_contact(self, account: str, sender: str) -> bool:
        """True if we have never seen this sender for this account before.

        This is a read; call note_sender() to record the sighting.
        """
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM senders WHERE account=? AND sender=?",
                (account, sender),
            ).fetchone()
        return row is None

    def note_sender(self, account: str, sender: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO senders(account, sender, first_seen) "
                "VALUES(?,?,?)",
                (account, sender, time.time()),
            )

    # --- Decisions & feedback --------------------------------------------

    def record(self, account: str, message: Message, verdict, fingerprint: str | None = None) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO decisions(account, message_id, sender, subject, "
                "is_cold, score, reasons, fingerprint, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(account, message_id) DO UPDATE SET "
                "is_cold=excluded.is_cold, score=excluded.score, "
                "reasons=excluded.reasons, fingerprint=excluded.fingerprint",
                (
                    account,
                    message.id,
                    message.sender,
                    message.subject,
                    int(verdict.is_cold),
                    float(verdict.score),
                    json.dumps(verdict.reasons),
                    fingerprint,
                    time.time(),
                ),
            )

    def record_feedback(self, account: str, message: Message, is_cold: bool) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO feedback(account, message_id, is_cold, created_at) "
                "VALUES(?,?,?,?)",
                (account, message.id, int(is_cold), time.time()),
            )

    def quarantined(self, account: str | None = None) -> list[dict]:
        """All messages currently recorded as cold — for the dashboard."""
        q = (
            "SELECT account, message_id, sender, subject, score, reasons, "
            "created_at FROM decisions WHERE is_cold=1"
        )
        params: tuple = ()
        if account:
            q += " AND account=?"
            params = (account,)
        q += " ORDER BY created_at DESC"
        with self._conn() as c:
            rows = c.execute(q, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["reasons"] = json.loads(d["reasons"])
            out.append(d)
        return out
