import sqlite3
import time
from pathlib import Path
from typing import Optional, Tuple, List

from .config import settings


class RecommendationFeedbackStore:
    """SQLite-backed store for recommendation feedback."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.UME_FEEDBACK_DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    timestamp INTEGER NOT NULL
                )
                """
            )

    def record(self, rec_id: str, status: str, *, timestamp: Optional[int] = None) -> None:
        ts = timestamp or int(time.time())
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO feedback(id, status, timestamp) VALUES(?,?,?)",
                (rec_id, status, ts),
            )

    def list_feedback(self) -> List[Tuple[str, str, int]]:
        cur = self.conn.execute("SELECT id, status, timestamp FROM feedback")
        return [(str(i), str(s), int(t)) for i, s, t in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()


feedback_store = RecommendationFeedbackStore()
