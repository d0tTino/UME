from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Any

from ..event import Event, parse_event
from ..processing import apply_event_to_graph
from ..persistent_graph import PersistentGraph
from ..snapshot import snapshot_graph_to_file, load_graph_from_file


class EpisodicMemory:
    """Event-sourced memory backed by :class:`PersistentGraph`."""

    def __init__(self, db_path: str | None = None, log_path: str | None = None) -> None:
        self.graph = PersistentGraph(db_path or ":memory:")
        self.log_path = Path(log_path) if log_path else None
        if self.log_path and self.log_path.is_file():
            self.load_events(str(self.log_path))

    def record_event(self, event: Event) -> None:
        """Apply ``event`` to the graph and append it to the log if configured."""
        apply_event_to_graph(event, self.graph)
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as f:
                json.dump(event.__dict__, f)
                f.write("\n")

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

    def close(self) -> None:
        self.graph.close()
