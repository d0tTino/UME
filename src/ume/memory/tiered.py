from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable

from ..config import settings
from ..metrics import STALE_VECTOR_WARNINGS
from ..vector_backends import VectorStore
from .episodic import EpisodicMemory
from .semantic import SemanticMemory
from .cold import ColdMemory

logger = logging.getLogger(__name__)


class TieredMemoryManager:
    """Coordinate episodic, semantic and cold storage layers."""

    def __init__(
        self,
        episodic: EpisodicMemory,
        semantic: SemanticMemory,
        *,
        cold: ColdMemory | None = None,
        vector_store: VectorStore | None = None,
        event_age_seconds: int = 7 * 86400,
        cold_age_seconds: int | None = settings.UME_COLD_EVENT_AGE_DAYS * 86400,
        vector_age_seconds: int | None = 30 * 86400,
        vector_check_interval: float = 24 * 3600,
    ) -> None:
        self.episodic = episodic
        self.semantic = semantic
        self.cold = cold
        self.vector_store = vector_store
        self.event_age_seconds = event_age_seconds
        self.cold_age_seconds = cold_age_seconds
        self.vector_age_seconds = vector_age_seconds
        self.vector_check_interval = vector_check_interval
        self._last_vector_check = 0.0
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def cycle(self) -> None:
        """Run a single aging cycle."""
        cutoff = int(time.time()) - self.event_age_seconds
        cur = self.episodic.graph.conn.execute(
            "SELECT id, attributes, created_at FROM nodes WHERE created_at < ? AND redacted=0",
            (cutoff,),
        )
        for row in cur.fetchall():
            self.semantic.add_fact(
                row["id"], json.loads(row["attributes"]), created_at=row["created_at"]
            )
        cur = self.episodic.graph.conn.execute(
            "SELECT source, target, label, created_at FROM edges WHERE created_at < ? AND redacted=0",
            (cutoff,),
        )
        for src, tgt, label, created_at in cur.fetchall():
            self.semantic.relate_facts(src, tgt, label, created_at=created_at)
        self.episodic.graph.purge_old_records(self.event_age_seconds)

        if self.cold is not None and self.cold_age_seconds is not None:
            cold_cutoff = int(time.time()) - self.cold_age_seconds
            cur = self.semantic.graph.conn.execute(
                "SELECT id, attributes, created_at FROM nodes WHERE created_at < ? AND redacted=0",
                (cold_cutoff,),
            )
            for row in cur.fetchall():
                self.cold.add_item(
                    row["id"], json.loads(row["attributes"]), created_at=row["created_at"]
                )
            cur = self.semantic.graph.conn.execute(
                "SELECT source, target, label, created_at FROM edges WHERE created_at < ? AND redacted=0",
                (cold_cutoff,),
            )
            for src, tgt, label, created_at in cur.fetchall():
                self.cold.relate_items(src, tgt, label, created_at=created_at)
            self.semantic.graph.purge_old_records(self.cold_age_seconds)

        if self.vector_store is not None and self.vector_age_seconds is not None:
            try:
                self.vector_store.expire_vectors(self.vector_age_seconds)
            except Exception:
                logger.exception("Failed to expire vectors")

        if self.vector_store is not None:
            now = time.time()
            if now - self._last_vector_check >= self.vector_check_interval:
                try:
                    timestamps = self.vector_store.get_vector_timestamps()
                    max_age = settings.UME_VECTOR_MAX_AGE_DAYS * 86400
                    stale = [vid for vid, ts in timestamps.items() if now - ts > max_age]
                    if stale:
                        STALE_VECTOR_WARNINGS.inc()
                        logger.warning("%s vectors exceed freshness limit", len(stale))
                except Exception:
                    logger.exception("Failed to check vector freshness")
                self._last_vector_check = now

    def start(
        self, *, interval_seconds: float = 3600
    ) -> tuple[threading.Thread, Callable[[], None]]:
        """Start a background thread that periodically runs :meth:`cycle`."""
        if self._thread and self._thread.is_alive():
            return self._thread, lambda: None

        self._stop_event.clear()

        def _run() -> None:
            try:
                self.cycle()
            except Exception:
                logger.exception("Tiered memory cycle failed")
            while not self._stop_event.wait(interval_seconds):
                try:
                    self.cycle()
                except Exception:
                    logger.exception("Tiered memory cycle failed")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        self._thread = thread

        def stop() -> None:
            self._stop_event.set()
            thread.join()

        return thread, stop

    def stop(self) -> None:
        """Stop the background thread if running."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
