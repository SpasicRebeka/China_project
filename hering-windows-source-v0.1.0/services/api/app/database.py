import hashlib
import json
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .schemas import RealtimeEnvelope, Role

SCHEMA_VERSION = 1
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    doctor_token_hash TEXT NOT NULL,
    patient_token_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'ended'))
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    source_role TEXT NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    envelope_json TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_events_session_time
ON events(session_id, occurred_at);
"""


@dataclass(frozen=True)
class CreatedSession:
    session_id: str
    doctor_token: str
    patient_token: str
    expires_at: datetime


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA_SQL)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now(UTC).isoformat()),
            )

    def is_ready(self) -> bool:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT MAX(version) AS version FROM schema_migrations"
                ).fetchone()
            return row is not None and row["version"] == SCHEMA_VERSION
        except sqlite3.Error:
            return False

    def create_session(self, ttl_minutes: int) -> CreatedSession:
        session_id = secrets.token_urlsafe(18)
        doctor_token = secrets.token_urlsafe(32)
        patient_token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=ttl_minutes)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(
                    id, doctor_token_hash, patient_token_hash, created_at, expires_at, status
                ) VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (
                    session_id,
                    _token_hash(doctor_token),
                    _token_hash(patient_token),
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
        return CreatedSession(session_id, doctor_token, patient_token, expires_at)

    def validate_token(self, session_id: str, role: Role, token: str) -> bool:
        column = "doctor_token_hash" if role == "doctor" else "patient_token_hash"
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {column}, expires_at, status FROM sessions WHERE id = ?",  # noqa: S608
                (session_id,),
            ).fetchone()
        if row is None or row["status"] != "active":
            return False
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC):
            return False
        return secrets.compare_digest(row[column], _token_hash(token))

    def record_event(self, envelope: RealtimeEnvelope) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO events(
                    event_id, session_id, source_role, event_type, occurred_at, envelope_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope.event_id,
                    envelope.session_id,
                    envelope.source_role,
                    envelope.type,
                    envelope.timestamp.isoformat(),
                    json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False),
                ),
            )
        return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0

    def event_count(self, session_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM events WHERE session_id = ?", (session_id,)
            ).fetchone()
        return int(row["count"]) if row else 0
