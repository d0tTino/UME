import atexit
import threading
import time
from pathlib import Path
from typing import Union
import logging
from .graph_adapter import IGraphAdapter
from .snapshot import snapshot_graph_to_file, load_graph_into_existing

logger = logging.getLogger(__name__)


def enable_periodic_snapshot(
    graph: IGraphAdapter, path: Union[str, Path], interval_seconds: int = 3600
) -> None:
    """Enable periodic snapshotting and snapshot on shutdown."""
    snapshot_path = Path(path)

    def _snapshot() -> None:
        try:
            snapshot_graph_to_file(graph, snapshot_path)
        except Exception:  # pragma: no cover - best effort
            pass

    def _run() -> None:
        while True:
            time.sleep(interval_seconds)
            _snapshot()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    atexit.register(_snapshot)


def enable_snapshot_autosave_and_restore(
    graph: IGraphAdapter, path: Union[str, Path], interval_seconds: int = 3600
) -> None:
    """Restore graph from snapshot if present and enable periodic autosave."""

    snapshot_path = Path(path)

    if snapshot_path.is_file():
        try:
            load_graph_into_existing(graph, snapshot_path)
        except Exception as e:  # pragma: no cover - logging only
            logger.warning("Failed to restore snapshot from %s: %s", snapshot_path, e)

    enable_periodic_snapshot(graph, snapshot_path, interval_seconds)
