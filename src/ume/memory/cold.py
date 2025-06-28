from __future__ import annotations

from typing import Any, Optional

from ..persistent_graph import PersistentGraph
from ..snapshot import snapshot_graph_to_file, load_graph_from_file


class ColdMemory:
    """Long-term cold storage backed by :class:`PersistentGraph`."""

    def __init__(self, db_path: str | None = None) -> None:
        self.graph = PersistentGraph(db_path or ":memory:", check_same_thread=False)

    def add_item(
        self, node_id: str, attributes: dict[str, Any], *, created_at: int | None = None
    ) -> None:
        self.graph.add_node(node_id, attributes, created_at=created_at)

    def relate_items(
        self, source_id: str, target_id: str, label: str, *, created_at: int | None = None
    ) -> None:
        self.graph.add_edge(source_id, target_id, label, created_at=created_at)

    def get_item(self, node_id: str) -> Optional[dict[str, Any]]:
        return self.graph.get_node(node_id)

    def related_items(self, node_id: str, label: str | None = None) -> list[str]:
        return self.graph.find_connected_nodes(node_id, edge_label=label)

    def save(self, path: str) -> None:
        snapshot_graph_to_file(self.graph, path)

    @classmethod
    def load(cls, path: str, db_path: str | None = None) -> "ColdMemory":
        graph = load_graph_from_file(path)
        mem = cls(db_path=db_path)
        mem.graph = graph
        return mem

    def close(self) -> None:
        self.graph.close()

