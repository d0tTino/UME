import logging
import threading
import time
from collections.abc import Callable

from typing import Protocol
from .config import settings
from .metrics import STALE_VECTOR_WARNINGS

logger = logging.getLogger(__name__)


_retention_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None
_vector_thread: threading.Thread | None = None
_vector_stop: threading.Event | None = None


class _SupportsPurge(Protocol):
    def purge_old_records(self, max_age_seconds: int) -> None:
        ...


class _SupportsVectorAge(Protocol):
    def get_vector_timestamps(self) -> dict[str, int]:
        ...


def start_retention_scheduler(
    graph: _SupportsPurge,
    *,
    interval_seconds: float = 24 * 3600,
) -> tuple[threading.Thread, Callable[[], None]]:
    """Start a background thread that periodically purges old graph records."""
    global _retention_thread, _stop_event

    if _retention_thread and _retention_thread.is_alive():
        return _retention_thread, lambda: None

    stop_event = threading.Event()

    retention_seconds = settings.UME_GRAPH_RETENTION_DAYS * 86400

    def _run() -> None:
        # Run once immediately so very short-lived tests can observe effects
        try:
            graph.purge_old_records(retention_seconds)
        except Exception:  # pragma: no cover - log and continue
            logger.exception("Failed to purge old graph records")

        while not stop_event.wait(interval_seconds):
            try:
                graph.purge_old_records(retention_seconds)
            except Exception:  # pragma: no cover - log and continue
                logger.exception("Failed to purge old graph records")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    _retention_thread = thread
    _stop_event = stop_event

    def stop() -> None:
        stop_event.set()
        thread.join()

    return thread, stop


def stop_retention_scheduler() -> None:
    """Stop the retention scheduler if running."""
    global _retention_thread, _stop_event

    if _stop_event is not None:
        _stop_event.set()
    if _retention_thread is not None:
        _retention_thread.join()
    _retention_thread = None
    _stop_event = None


def _check_stale_vectors(store: _SupportsVectorAge, *, log: bool, threshold: int) -> None:
    max_age = settings.UME_VECTOR_MAX_AGE_DAYS * 86400
    now = int(time.time())
    timestamps = store.get_vector_timestamps()
    stale = [vid for vid, ts in timestamps.items() if now - ts > max_age]
    if len(stale) > threshold:
        STALE_VECTOR_WARNINGS.inc()
        if log:
            logger.warning("%s stale vectors detected", len(stale))


def start_vector_age_scheduler(
    store: _SupportsVectorAge,
    *,
    interval_seconds: float = 24 * 3600,
    warn_threshold: int = 0,
    log: bool = False,
) -> tuple[threading.Thread, Callable[[], None]]:
    global _vector_thread, _vector_stop

    if _vector_thread and _vector_thread.is_alive():
        return _vector_thread, lambda: None

    stop_event = threading.Event()

    def _run() -> None:
        while not stop_event.wait(interval_seconds):
            try:
                _check_stale_vectors(store, log=log, threshold=warn_threshold)
            except Exception:
                logger.exception("Failed to check vector age")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    _vector_thread = thread
    _vector_stop = stop_event

    def stop() -> None:
        stop_event.set()
        thread.join()

    return thread, stop


def stop_vector_age_scheduler() -> None:
    global _vector_thread, _vector_stop
    if _vector_stop is not None:
        _vector_stop.set()
    if _vector_thread is not None:
        _vector_thread.join()
    _vector_thread = None
    _vector_stop = None
