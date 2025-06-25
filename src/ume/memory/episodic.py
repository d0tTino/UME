from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional, Any, List

from ..event import Event, parse_event
from ..processing import apply_event_to_graph
from ..persistent_graph import PersistentGraph
from ..snapshot import snapshot_graph_to_file, load_graph_from_file


class EpisodicMemory:
    """Event-sourced memory backed by :class:`PersistentGraph`."""

    def __init__(
        self,
        db_path: str | None = None,
        log_path: str | None = None,
        *,
        flush_interval: float | None = None,
    ) -> None:
        self.graph = PersistentGraph(db_path or ":memory:")
        self.log_path = Path(log_path) if log_path else None
        self._buffer: List[Event] = []
        self._flush_interval = flush_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        if self.log_path:
            self._replay_logs()
            if flush_interval and flush_interval > 0:
                self._thread = threading.Thread(target=self._flush_loop, daemon=True)
                self._thread.start()

    def record_event(self, event: Event) -> None:
        """Apply ``event`` to the graph and queue it for flushing."""
        apply_event_to_graph(event, self.graph)
        if self.log_path is not None:
            self._buffer.append(event)
            if not self._thread:
                self.flush()

    def _flush_loop(self) -> None:
        while not self._stop_event.wait(self._flush_interval):
            self.flush()

    def flush(self) -> None:
        if not self.log_path or not self._buffer:
            return
        with self.log_path.open("a", encoding="utf-8") as f:
            for evt in self._buffer:
                json.dump(evt.__dict__, f)
                f.write("\n")
        self._buffer.clear()

    def load_events(self, log_path: str) -> None:
        """Replay events from ``log_path`` into the graph."""
        path = Path(log_path)
        if not path.is_file():
            return
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                evt = parse_event(data)
                apply_event_to_graph(evt, self.graph)

    def _replay_logs(self) -> None:
        if not self.log_path:
            return
        pattern = f"{self.log_path.stem}*{self.log_path.suffix}"
        logs = sorted(
            self.log_path.parent.glob(pattern), key=lambda p: p.stat().st_mtime
        )
        for log_file in logs:
            self.load_events(str(log_file))

    def get_episode(self, node_id: str) -> Optional[dict[str, Any]]:
        return self.graph.get_node(node_id)

    def related(self, node_id: str, label: str | None = None) -> list[str]:
        return self.graph.find_connected_nodes(node_id, edge_label=label)

    def save(self, path: str) -> None:
        snapshot_graph_to_file(self.graph, path)

    @classmethod
    def load(cls, path: str, db_path: str | None = None, log_path: str | None = None) -> "EpisodicMemory":
        graph = load_graph_from_file(path)
        mem = cls(db_path=db_path, log_path=log_path)
        mem.graph = graph
        return mem

    def rotate_logs(
        self, *, max_bytes: int | None = None, max_age_seconds: int | None = None
    ) -> None:
        if not self.log_path or not self.log_path.exists():
            return
        stat = self.log_path.stat()
        rotate = False
        if max_bytes is not None and stat.st_size >= max_bytes:
            rotate = True
        if max_age_seconds is not None and time.time() - stat.st_mtime >= max_age_seconds:
            rotate = True
        if not rotate:
            return
        self.flush()
        rotated = self.log_path.with_name(
            f"{self.log_path.stem}.{int(time.time())}{self.log_path.suffix}"
        )
        self.log_path.rename(rotated)

    def close(self) -> None:
        self.flush()
        if self._thread:
            self._stop_event.set()
            self._thread.join()
        self.graph.close()
