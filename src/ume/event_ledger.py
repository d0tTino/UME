from __future__ import annotations

import json
import sqlite3
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing import
    from cryptography.fernet import Fernet
    from .vector_outbox import VectorOutboxRecord
else:  # pragma: no cover - cryptography optional
    try:
        from cryptography.fernet import Fernet  # type: ignore
    except Exception:
        Fernet = None  # type: ignore[assignment]

from .config import settings


class EventLedger:
    """Persist sanitized events with their Redpanda offsets."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.UME_EVENT_LEDGER_PATH
        self.encryption_enabled = settings.UME_ENCRYPTION_ENABLED
        if self.encryption_enabled:
            if Fernet is None or not settings.UME_ENCRYPTION_KEY:
                raise ValueError("Encryption enabled but cryptography not available or key not set")
            self._fernet = Fernet(settings.UME_ENCRYPTION_KEY.encode())
            self._plain_path = self.db_path + ".dec"
            Path(self._plain_path).parent.mkdir(parents=True, exist_ok=True)
            if os.path.exists(self.db_path):
                with open(self.db_path, "rb") as f:
                    data = f.read()
                if data:
                    decrypted = self._fernet.decrypt(data)
                else:
                    decrypted = b""
                with open(self._plain_path, "wb") as f:
                    f.write(decrypted)
            self.conn = sqlite3.connect(self._plain_path, check_same_thread=False)
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_table()
        self._last_processed_offset = self._load_bookmark()

    def _create_table(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    offset INTEGER PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bookmark (
                    id INTEGER PRIMARY KEY CHECK (id=0),
                    last_offset INTEGER
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ledger_offset INTEGER,
                    event_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    available_at REAL NOT NULL,
                    delivered_at REAL,
                    last_error TEXT
                )
                """
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vector_outbox_pending ON vector_outbox (state, available_at, id)"
            )

    def append(self, offset: int, event: Dict[str, Any]) -> None:
        with self.conn:
            try:
                self.conn.execute(
                    "INSERT INTO events(offset, data) VALUES (?, ?)",
                    (offset, json.dumps(event)),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Offset {offset} already exists") from exc

    def range(
        self,
        start: int = 0,
        end: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Tuple[int, Dict[str, Any]]]:
        query = "SELECT offset, data FROM events WHERE offset >= ?"
        params: List[Any] = [start]
        if end is not None:
            query += " AND offset <= ?"
            params.append(end)
        query += " ORDER BY offset"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        cur = self.conn.execute(query, params)
        return [
            (int(row["offset"]), json.loads(row["data"])) for row in cur.fetchall()
        ]

    def max_offset(self) -> int:
        cur = self.conn.execute("SELECT MAX(offset) FROM events")
        row = cur.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return -1

    # Bookmark persistence -------------------------------------------------
    def _load_bookmark(self) -> int:
        cur = self.conn.execute("SELECT last_offset FROM bookmark WHERE id=0")
        row = cur.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return -1

    @property
    def last_processed_offset(self) -> int:
        return self._last_processed_offset

    def update_bookmark(self, offset: int) -> None:
        if offset < 0:
            raise ValueError("offset must be non-negative")
        with self.conn:
            self.conn.execute(
                "INSERT INTO bookmark(id, last_offset) VALUES(0, ?) "
                "ON CONFLICT(id) DO UPDATE SET last_offset=excluded.last_offset",
                (offset,),
            )
        self._last_processed_offset = offset

    # ---------------------------------------------------------------------

    def compact(self, max_offset: int) -> None:
        """Delete events with offsets lower than ``max_offset``."""
        with self.conn:
            self.conn.execute("DELETE FROM events WHERE offset < ?", (max_offset,))

    def enqueue_vector_outbox(
        self,
        *,
        ledger_offset: int | None,
        event_id: str,
        node_id: str,
        embedding: list[float],
        idempotency_key: str,
        created_at: float | None = None,
    ) -> None:
        now = created_at if created_at is not None else time.time()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO vector_outbox(
                    ledger_offset, event_id, node_id, embedding_json, idempotency_key,
                    state, attempts, created_at, available_at
                ) VALUES(?, ?, ?, ?, ?, 'pending', 0, ?, ?)
                ON CONFLICT(idempotency_key) DO NOTHING
                """,
                (ledger_offset, event_id, node_id, json.dumps(embedding), idempotency_key, now, now),
            )

    def get_pending_vector_outbox(
        self,
        *,
        limit: int,
        now_ts: float | None = None,
    ) -> list["VectorOutboxRecord"]:
        from .vector_outbox import VectorOutboxRecord

        now = now_ts if now_ts is not None else time.time()
        cur = self.conn.execute(
            """
            SELECT id, ledger_offset, event_id, node_id, embedding_json, idempotency_key, attempts, available_at
            FROM vector_outbox
            WHERE state='pending' AND available_at <= ?
            ORDER BY id
            LIMIT ?
            """,
            (now, limit),
        )
        return [
            VectorOutboxRecord(
                id=int(row["id"]),
                ledger_offset=int(row["ledger_offset"]) if row["ledger_offset"] is not None else None,
                event_id=str(row["event_id"]),
                node_id=str(row["node_id"]),
                embedding=list(json.loads(row["embedding_json"])),
                idempotency_key=str(row["idempotency_key"]),
                attempts=int(row["attempts"]),
                available_at=float(row["available_at"]),
            )
            for row in cur.fetchall()
        ]

    def mark_vector_outbox_delivered(self, record_id: int, *, delivered_at: float | None = None) -> None:
        ts = delivered_at if delivered_at is not None else time.time()
        with self.conn:
            self.conn.execute(
                "UPDATE vector_outbox SET state='delivered', delivered_at=?, last_error=NULL WHERE id=?",
                (ts, record_id),
            )

    def fail_vector_outbox_delivery(self, *, record_id: int, error: str, now_ts: float | None = None) -> None:
        now = now_ts if now_ts is not None else time.time()
        with self.conn:
            cur = self.conn.execute("SELECT attempts FROM vector_outbox WHERE id=?", (record_id,))
            row = cur.fetchone()
            if row is None:
                return
            attempts = int(row["attempts"]) + 1
            backoff_seconds = float(min(60, 2 ** min(attempts, 6)))
            available_at = now + backoff_seconds
            self.conn.execute(
                """
                UPDATE vector_outbox
                SET attempts=?, last_error=?, available_at=?, state='pending'
                WHERE id=?
                """,
                (attempts, error[:1024], available_at, record_id),
            )

    def vector_outbox_pending_count(self, *, now_ts: float | None = None) -> int:
        now = now_ts if now_ts is not None else time.time()
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM vector_outbox WHERE state='pending' AND available_at <= ?",
            (now,),
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def vector_outbox_max_lag_seconds(self, *, now_ts: float | None = None) -> float:
        now = now_ts if now_ts is not None else time.time()
        cur = self.conn.execute(
            "SELECT MIN(created_at) FROM vector_outbox WHERE state='pending'"
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            return 0.0
        return max(now - float(row[0]), 0.0)

    def vector_outbox_created_at(self, record_id: int) -> float | None:
        cur = self.conn.execute("SELECT created_at FROM vector_outbox WHERE id=?", (record_id,))
        row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return float(row[0])

    def iter_vector_outbox_for_replay(self, *, end_offset: int | None = None) -> list["VectorOutboxRecord"]:
        from .vector_outbox import VectorOutboxRecord

        query = (
            "SELECT id, ledger_offset, event_id, node_id, embedding_json, idempotency_key, attempts, available_at "
            "FROM vector_outbox WHERE state='delivered'"
        )
        params: list[Any] = []
        if end_offset is not None:
            query += " AND ledger_offset IS NOT NULL AND ledger_offset <= ?"
            params.append(end_offset)
        query += " ORDER BY COALESCE(ledger_offset, 9223372036854775807), id"
        cur = self.conn.execute(query, params)
        return [
            VectorOutboxRecord(
                id=int(row["id"]),
                ledger_offset=int(row["ledger_offset"]) if row["ledger_offset"] is not None else None,
                event_id=str(row["event_id"]),
                node_id=str(row["node_id"]),
                embedding=list(json.loads(row["embedding_json"])),
                idempotency_key=str(row["idempotency_key"]),
                attempts=int(row["attempts"]),
                available_at=float(row["available_at"]),
            )
            for row in cur.fetchall()
        ]

    def close(self) -> None:
        self.conn.close()
        if self.encryption_enabled:
            with open(self._plain_path, "rb") as f:
                data = f.read()
            encrypted = self._fernet.encrypt(data)
            tmp_dir = Path(self.db_path).parent
            tmp_file = tempfile.NamedTemporaryFile(
                "wb", delete=False, dir=tmp_dir
            )
            try:
                with tmp_file:
                    tmp_file.write(encrypted)
                os.replace(tmp_file.name, self.db_path)
            finally:
                if os.path.exists(tmp_file.name):
                    os.remove(tmp_file.name)
            if os.path.exists(self._plain_path):
                os.remove(self._plain_path)


# Global ledger instance used by graph consumers
event_ledger = EventLedger()
