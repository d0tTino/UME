from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from .config import settings


class EventLedger:
    """Persist sanitized events with their Redpanda offsets."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.UME_EVENT_LEDGER_PATH
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

    def close(self) -> None:
        self.conn.close()


# Global ledger instance used by graph consumers
event_ledger = EventLedger()
