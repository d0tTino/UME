import logging
import threading
from collections.abc import Callable

from typing import Any
from .config import settings

logger = logging.getLogger(__name__)


_retention_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None


def start_retention_scheduler(
    graph: Any,
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
