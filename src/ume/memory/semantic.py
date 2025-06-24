from __future__ import annotations

from typing import Optional, Any

from ..persistent_graph import PersistentGraph
from ..snapshot import snapshot_graph_to_file, load_graph_from_file


class SemanticMemory:
    """Fact storage backed by :class:`PersistentGraph`."""

    def __init__(self, db_path: str | None = None) -> None:
        self.graph = PersistentGraph(db_path or ":memory:")

    def add_fact(self, node_id: str, attributes: dict[str, Any]) -> None:
        self.graph.add_node(node_id, attributes)

    def relate_facts(self, source_id: str, target_id: str, label: str) -> None:
        self.graph.add_edge(source_id, target_id, label)

    def get_fact(self, node_id: str) -> Optional[dict[str, Any]]:
        return self.graph.get_node(node_id)

    def related_facts(self, node_id: str, label: str | None = None) -> list[str]:
        return self.graph.find_connected_nodes(node_id, edge_label=label)

    def save(self, path: str) -> None:
        snapshot_graph_to_file(self.graph, path)

    @classmethod
    def load(cls, path: str, db_path: str | None = None) -> "SemanticMemory":
        graph = load_graph_from_file(path)
        mem = cls(db_path=db_path)
        mem.graph = graph
        return mem

    def close(self) -> None:
        self.graph.close()
