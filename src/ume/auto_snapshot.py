import atexit
import threading
from pathlib import Path
from typing import Union
import logging
from collections.abc import Callable
from .graph_adapter import IGraphAdapter
from .snapshot import snapshot_graph_to_file, load_graph_into_existing

logger = logging.getLogger(__name__)


_periodic_snapshot_thread: threading.Thread | None = None
_periodic_snapshot_stop_event: threading.Event | None = None
_atexit_handle: Callable[[], object] | None = None


def enable_periodic_snapshot(
    graph: IGraphAdapter, path: Union[str, Path], interval_seconds: int = 3600
) -> tuple[threading.Thread, Callable[[], None]]:
    """Enable periodic snapshotting and snapshot on shutdown.

    Returns the background thread used for snapshotting and a function to stop
    it.
    """
    global _periodic_snapshot_thread, _periodic_snapshot_stop_event, _atexit_handle

    snapshot_path = Path(path)

    def _snapshot() -> None:
        try:
            snapshot_graph_to_file(graph, snapshot_path)
        except Exception:  # pragma: no cover - don't raise during shutdown
            logger.exception("Failed to snapshot graph to %s", snapshot_path)

    stop_event = threading.Event()

    def _run() -> None:
        while not stop_event.wait(interval_seconds):
            _snapshot()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    _atexit_handle = atexit.register(_snapshot)

    _periodic_snapshot_thread = thread
    _periodic_snapshot_stop_event = stop_event

    def stop() -> None:
        stop_event.set()
        thread.join()

    return thread, stop


def disable_periodic_snapshot() -> None:
    """Stop the periodic snapshot thread if running."""
    global _periodic_snapshot_thread, _periodic_snapshot_stop_event, _atexit_handle

    if _periodic_snapshot_stop_event is not None:
        _periodic_snapshot_stop_event.set()
    if _periodic_snapshot_thread is not None:
        _periodic_snapshot_thread.join()
    if _atexit_handle is not None:
        try:
            atexit.unregister(_atexit_handle)
        finally:
            _atexit_handle = None

    _periodic_snapshot_thread = None
    _periodic_snapshot_stop_event = None


def enable_snapshot_autosave_and_restore(
    graph: IGraphAdapter, path: Union[str, Path], interval_seconds: int = 3600
) -> tuple[threading.Thread, Callable[[], None]]:
    """Restore graph from snapshot if present and enable periodic autosave."""

    snapshot_path = Path(path)

    if snapshot_path.is_file():
        try:
            load_graph_into_existing(graph, snapshot_path)
        except Exception as e:  # pragma: no cover - logging only
            logger.warning("Failed to restore snapshot from %s: %s", snapshot_path, e)

    return enable_periodic_snapshot(graph, snapshot_path, interval_seconds)
