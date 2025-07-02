import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from .memory import EpisodicMemory, SemanticMemory, ColdMemory
from .vector_store import VectorStore
from .config import settings
from .metrics import STALE_VECTOR_WARNINGS, STALE_VECTOR_COUNT

logger = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None
_thread_params: tuple[Any, ...] | None = None
_vector_thread: threading.Thread | None = None
_vector_stop: threading.Event | None = None
_vector_params: tuple[Any, ...] | None = None


def start_memory_aging_scheduler(
    episodic: EpisodicMemory,
    semantic: SemanticMemory,
    *,
    cold: ColdMemory | None = None,
    vector_store: VectorStore | None = None,
    event_age_seconds: int = 7 * 86400,
    cold_age_seconds: int | None = settings.UME_COLD_EVENT_AGE_DAYS * 86400,
    vector_age_seconds: int | None = 30 * 86400,
    interval_seconds: float = 3600,
    vector_check_interval: float = 24 * 3600,
) -> tuple[threading.Thread, Callable[[], None]]:
    """Move aged events to long-term storage and prune stale vectors.

    Records first migrate from episodic to semantic memory. Items older than
    ``cold_age_seconds`` are moved from semantic to cold storage. Vector data is
    expired using ``VectorStore.expire_vectors`` and checked nightly for
    freshness limits.

    Pass ``vector_age_seconds=None`` to skip vector expiration checks.
    """
    global _thread, _stop_event, _thread_params

    params = (
        episodic,
        semantic,
        cold,
        vector_store,
        event_age_seconds,
        cold_age_seconds,
        vector_age_seconds,
        interval_seconds,
        vector_check_interval,
    )

    if _thread and _thread.is_alive():
        if params == _thread_params:
            return _thread, lambda: None
        stop_memory_aging_scheduler()

    stop_event = threading.Event()
    last_vector_check = 0.0

    def _cycle() -> None:
        cutoff = int(time.time()) - event_age_seconds
        cur = episodic.graph.conn.execute(
            "SELECT id, attributes, created_at FROM nodes WHERE created_at < ? AND redacted=0",
            (cutoff,),
        )
        for row in cur.fetchall():
            node_id = row["id"]
            attrs = json.loads(row["attributes"])
            semantic.add_fact(node_id, attrs, created_at=row["created_at"])
        cur = episodic.graph.conn.execute(
            "SELECT source, target, label, created_at FROM edges WHERE created_at < ? AND redacted=0",
            (cutoff,),
        )
        for src, tgt, label, created_at in cur.fetchall():
            semantic.relate_facts(src, tgt, label, created_at=created_at)
        episodic.graph.purge_old_records(event_age_seconds)

        if cold is not None and cold_age_seconds is not None:
            cold_cutoff = int(time.time()) - cold_age_seconds
            cur = semantic.graph.conn.execute(
                "SELECT id, attributes, created_at FROM nodes WHERE created_at < ? AND redacted=0",
                (cold_cutoff,),
            )
            for row in cur.fetchall():
                cold.add_item(
                    row["id"],
                    json.loads(row["attributes"]),
                    created_at=row["created_at"],
                )
            cur = semantic.graph.conn.execute(
                "SELECT source, target, label, created_at FROM edges WHERE created_at < ? AND redacted=0",
                (cold_cutoff,),
            )
            for src, tgt, label, created_at in cur.fetchall():
                cold.relate_items(src, tgt, label, created_at=created_at)
            semantic.graph.purge_old_records(cold_age_seconds)

        if vector_store is not None and vector_age_seconds is not None:
            try:
                vector_store.expire_vectors(vector_age_seconds)
            except Exception:
                logger.exception("Failed to expire vectors")

        if vector_store is not None:
            nonlocal last_vector_check
            now = time.time()
            if now - last_vector_check >= vector_check_interval:
                try:
                    timestamps = vector_store.get_vector_timestamps()
                    max_age = settings.UME_VECTOR_MAX_AGE_DAYS * 86400
                    stale = [vid for vid, ts in timestamps.items() if now - ts > max_age]
                    if stale:
                        STALE_VECTOR_WARNINGS.inc()
                        logger.warning("%s vectors exceed freshness limit", len(stale))
                except Exception:
                    logger.exception("Failed to check vector freshness")
                last_vector_check = now

    def _run() -> None:
        try:
            _cycle()
        except Exception:
            logger.exception("Memory aging cycle failed")
        while not stop_event.wait(interval_seconds):
            try:
                _cycle()
            except Exception:
                logger.exception("Memory aging cycle failed")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    _thread = thread
    _stop_event = stop_event
    _thread_params = params

    def stop() -> None:
        stop_event.set()
        thread.join()

    return thread, stop


def _check_stale_vectors(
    store: VectorStore,
    *,
    warn_threshold: int,
    log: bool,
) -> None:
    now = int(time.time())
    max_age = settings.UME_VECTOR_MAX_AGE_DAYS * 86400
    timestamps = store.get_vector_timestamps()
    stale = [vid for vid, ts in timestamps.items() if now - ts > max_age]
    STALE_VECTOR_COUNT.set(len(stale))
    if len(stale) > warn_threshold:
        STALE_VECTOR_WARNINGS.inc()
        if log:
            logger.warning("%s stale vectors detected", len(stale))


def start_vector_age_scheduler(
    store: VectorStore,
    *,
    interval_seconds: float = 24 * 3600,
    warn_threshold: int = 0,
    log: bool = False,
) -> tuple[threading.Thread, Callable[[], None]]:
    """Periodically check vector age and record metrics."""
    global _vector_thread, _vector_stop, _vector_params

    params = (store, interval_seconds, warn_threshold, log)

    if _vector_thread and _vector_thread.is_alive():
        if params == _vector_params:
            return _vector_thread, lambda: None
        stop_vector_age_scheduler()

    stop_event = threading.Event()

    def _run() -> None:
        while not stop_event.wait(interval_seconds):
            try:
                _check_stale_vectors(
                    store,
                    warn_threshold=warn_threshold,
                    log=log,
                )
            except Exception:  # pragma: no cover - log and continue
                logger.exception("Failed to check vector age")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    _vector_thread = thread
    _vector_stop = stop_event
    _vector_params = params

    def stop() -> None:
        stop_event.set()
        thread.join()

    return thread, stop


def stop_vector_age_scheduler() -> None:
    """Stop the vector age scheduler if running."""
    global _vector_thread, _vector_stop, _vector_params
    if _vector_stop is not None:
        _vector_stop.set()
    if _vector_thread is not None:
        _vector_thread.join()
    _vector_thread = None
    _vector_stop = None
    _vector_params = None


def stop_memory_aging_scheduler() -> None:
    """Stop the memory aging scheduler if running."""
    global _thread, _stop_event, _thread_params

    if _stop_event is not None:
        _stop_event.set()
    if _thread is not None:
        _thread.join()
    _thread = None
    _stop_event = None
    _thread_params = None
