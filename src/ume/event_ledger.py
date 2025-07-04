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

    def append(self, offset: int, event: Dict[str, Any]) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO events(offset, data) VALUES (?, ?)",
                (offset, json.dumps(event)),
            )

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

    def close(self) -> None:
        self.conn.close()


# Global ledger instance used by graph consumers
event_ledger = EventLedger()
