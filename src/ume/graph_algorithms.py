from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, cast

from .processing import ProcessingError
from .graph_adapter import IGraphAdapter


def shortest_path(graph: IGraphAdapter, source_id: str, target_id: str) -> List[str]:
    """Return the shortest path from ``source_id`` to ``target_id``."""
    if not graph.node_exists(source_id) or not graph.node_exists(target_id):
        return []
    visited: Dict[str, Optional[str]] = {source_id: None}
    queue: List[str] = [source_id]
    while queue:
        current = queue.pop(0)
        if current == target_id:
            break
        for neighbor in graph.find_connected_nodes(current):
            if neighbor not in visited:
                visited[neighbor] = current
                queue.append(neighbor)
    if target_id not in visited:
        return []
    path = [target_id]
    while visited[path[-1]] is not None:
        prev = visited[path[-1]]
        assert prev is not None
        path.append(prev)
    path.reverse()
    return path


def traverse(
    graph: IGraphAdapter,
    start_node_id: str,
    depth: int,
    edge_label: Optional[str] = None,
) -> List[str]:
    """Breadth-first traversal from ``start_node_id`` up to ``depth`` hops."""
    if not graph.node_exists(start_node_id):
        raise ProcessingError(f"Node '{start_node_id}' not found.")
    visited: set[str] = {start_node_id}
    queue: List[tuple[str, int]] = [(start_node_id, 0)]
    result: List[str] = []
    while queue:
        node, d = queue.pop(0)
        if d >= depth:
            continue
        for neighbor in graph.find_connected_nodes(node, edge_label):
            if neighbor not in visited:
                visited.add(neighbor)
                result.append(neighbor)
                queue.append((neighbor, d + 1))
    return result


def extract_subgraph(
    graph: IGraphAdapter,
    start_node_id: str,
    depth: int,
    edge_label: Optional[str] = None,
    since_timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """Return a dictionary describing a subgraph rooted at ``start_node_id``."""
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Tuple[str, str, str]] = []
    adj: Dict[str, List[Tuple[str, str]]] = {}
    for src, tgt, lbl in graph.get_all_edges():
        adj.setdefault(src, []).append((tgt, lbl))

    to_visit = [(start_node_id, 0)]
    visited: set[str] = set()
    while to_visit:
        node, d = to_visit.pop(0)
        if node in visited or d > depth:
            continue
        visited.add(node)
        data = graph.get_node(node) or {}
        include = True
        if since_timestamp is not None:
            ts = data.get("timestamp")
            if ts is None or int(ts) < since_timestamp:
                include = False
        if include:
            nodes[node] = data.copy()
        if d == depth:
            continue
        for tgt, lbl in adj.get(node, []):
            if edge_label is None or lbl == edge_label:
                edges.append((node, tgt, lbl))
                to_visit.append((tgt, d + 1))
    return {"nodes": nodes, "edges": edges}


class GraphAlgorithmsMixin:
    """Reusable traversal and path finding methods for graph adapters."""

    # These methods are expected to be provided by the implementing graph adapter
    def node_exists(self, node_id: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def find_connected_nodes(
        self, node_id: str, edge_label: Optional[str] = None
    ) -> List[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def get_all_edges(self) -> List[Tuple[str, str, str]]:  # pragma: no cover
        raise NotImplementedError

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def shortest_path(self, source_id: str, target_id: str) -> List[str]:
        return shortest_path(cast(IGraphAdapter, self), source_id, target_id)

    def traverse(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
    ) -> List[str]:
        return traverse(cast(IGraphAdapter, self), start_node_id, depth, edge_label)

    def extract_subgraph(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
        since_timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        return extract_subgraph(
            cast(IGraphAdapter, self), start_node_id, depth, edge_label, since_timestamp
        )

    def constrained_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: Optional[int] = None,
        edge_label: Optional[str] = None,
        since_timestamp: Optional[int] = None,
    ) -> List[str]:
        if not self.node_exists(source_id) or not self.node_exists(target_id):
            return []
        visited: Dict[str, Optional[str]] = {source_id: None}
        queue: List[tuple[str, int]] = [(source_id, 0)]
        while queue:
            node, depth = queue.pop(0)
            if node == target_id:
                break
            if max_depth is not None and depth >= max_depth:
                continue
            for neighbor in self.find_connected_nodes(node, edge_label):
                if neighbor in visited:
                    continue
                if since_timestamp is not None:
                    data = self.get_node(neighbor) or {}
                    ts = data.get("timestamp")
                    if ts is None or int(ts) < since_timestamp:
                        continue
                visited[neighbor] = node
                queue.append((neighbor, depth + 1))
        if target_id not in visited:
            return []
        path = [target_id]
        while visited[path[-1]] is not None:
            prev = visited[path[-1]]
            assert prev is not None
            path.append(prev)
        path.reverse()
        return path
