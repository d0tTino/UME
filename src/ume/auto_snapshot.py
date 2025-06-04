import atexit
import threading
import time
from pathlib import Path
from typing import Union
from .graph_adapter import IGraphAdapter
from .snapshot import snapshot_graph_to_file


def enable_periodic_snapshot(graph: IGraphAdapter, path: Union[str, Path], interval_seconds: int = 3600) -> None:
    """Enable periodic snapshotting and snapshot on shutdown."""
    snapshot_path = Path(path)

    def _snapshot() -> None:
        snapshot_graph_to_file(graph, snapshot_path)

    def _run() -> None:
        while True:
            time.sleep(interval_seconds)
            _snapshot()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    atexit.register(_snapshot)
