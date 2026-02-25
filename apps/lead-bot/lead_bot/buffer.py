from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass


@dataclass
class BufferedLead:
    row_id: int
    payload: dict
    idempotency_key: str


class LeadBuffer:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_buffer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def add(self, payload: dict, idempotency_key: str | None = None) -> None:
        key = idempotency_key or str(uuid.uuid4())
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO lead_buffer (created_at, payload_json, idempotency_key) VALUES (?, ?, ?)",
                (int(time.time()), json.dumps(payload, ensure_ascii=False), key),
            )
            conn.commit()

    def fetch_oldest(self) -> list[BufferedLead]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, payload_json, idempotency_key FROM lead_buffer ORDER BY id ASC"
            ).fetchall()
        return [BufferedLead(row_id=row[0], payload=json.loads(row[1]), idempotency_key=row[2]) for row in rows]

    def delete(self, row_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM lead_buffer WHERE id = ?", (row_id,))
            conn.commit()
