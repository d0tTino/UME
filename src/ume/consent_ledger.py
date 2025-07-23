from __future__ import annotations

import sqlite3
import time
import os
from pathlib import Path
from typing import Optional

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover - cryptography optional
    Fernet = None

from .config import settings


class ConsentLedger:
    """Simple ledger tracking user consents by scope."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.UME_CONSENT_LEDGER_PATH
        self.encryption_enabled = settings.UME_ENCRYPTION_ENABLED
        if self.encryption_enabled:
            if not (Fernet and settings.UME_ENCRYPTION_KEY):
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

    def list_consents(self) -> list[tuple[str, str, int]]:
        """Return all stored consent entries."""
        cur = self.conn.execute("SELECT user_id, scope, timestamp FROM consent")
        rows = cur.fetchall()
        return [(str(u), str(s), int(t)) for u, s, t in rows]

    def close(self) -> None:
        self.conn.close()
        if self.encryption_enabled:
            with open(self._plain_path, "rb") as f:
                data = f.read()
            encrypted = self._fernet.encrypt(data)
            with open(self.db_path, "wb") as f:
                f.write(encrypted)
            if os.path.exists(self._plain_path):
                os.remove(self._plain_path)


# Global ledger instance used by the privacy agent
consent_ledger = ConsentLedger()
