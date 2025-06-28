from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from .config import settings


class ConsentLedger:
    """Simple ledger tracking user consents by scope."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.UME_CONSENT_LEDGER_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._create_table()

    def _create_table(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS consent (
                    user_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    PRIMARY KEY (user_id, scope)
                )
                """
            )

    def give_consent(
        self, user_id: str, scope: str, *, timestamp: Optional[int] = None
    ) -> None:
        ts = timestamp or int(time.time())
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO consent(user_id, scope, timestamp) VALUES(?,?,?)",
                (user_id, scope, ts),
            )

    def revoke_consent(self, user_id: str, scope: str) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM consent WHERE user_id=? AND scope=?",
                (user_id, scope),
            )

    def has_consent(self, user_id: str, scope: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM consent WHERE user_id=? AND scope=?",
            (user_id, scope),
        )
        return cur.fetchone() is not None

    def close(self) -> None:
        self.conn.close()


# Global ledger instance used by the privacy agent
consent_ledger = ConsentLedger()
