import json
import logging
import threading
import time
from collections.abc import Callable

from .memory import EpisodicMemory, SemanticMemory
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None


def start_memory_aging_scheduler(
    episodic: EpisodicMemory,
    semantic: SemanticMemory,
    *,
    vector_store: VectorStore | None = None,
    event_age_seconds: int = 7 * 86400,
    vector_age_seconds: int | None = 30 * 86400,
    interval_seconds: float = 3600,
) -> tuple[threading.Thread, Callable[[], None]]:
    """Move aged events to long-term storage and prune stale vectors.

    Pass ``vector_age_seconds=None`` to skip vector expiration checks.
    """
    global _thread, _stop_event

    if _thread and _thread.is_alive():
        return _thread, lambda: None

    stop_event = threading.Event()

    def _cycle() -> None:
        cutoff = int(time.time()) - event_age_seconds
        cur = episodic.graph.conn.execute(
            "SELECT id, attributes FROM nodes WHERE created_at < ? AND redacted=0",
            (cutoff,),
        )
        for row in cur.fetchall():
            node_id = row["id"]
            attrs = json.loads(row["attributes"])
            semantic.add_fact(node_id, attrs)
        cur = episodic.graph.conn.execute(
            "SELECT source, target, label FROM edges WHERE created_at < ? AND redacted=0",
            (cutoff,),
        )
        for src, tgt, label in cur.fetchall():
            semantic.relate_facts(src, tgt, label)
        episodic.graph.purge_old_records(event_age_seconds)
        if vector_store is not None and vector_age_seconds is not None:
            try:
                vector_store.expire_vectors(vector_age_seconds)
            except Exception:
                logger.exception("Failed to expire vectors")

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

    def stop() -> None:
        stop_event.set()
        thread.join()

    return thread, stop


def stop_memory_aging_scheduler() -> None:
    """Stop the memory aging scheduler if running."""
    global _thread, _stop_event

    if _stop_event is not None:
        _stop_event.set()
    if _thread is not None:
        _thread.join()
    _thread = None
    _stop_event = None
