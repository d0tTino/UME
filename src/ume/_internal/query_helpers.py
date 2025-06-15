from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..graph_adapter import IGraphAdapter
from ..graph_algorithms import (
    shortest_path as _shortest_path,
    traverse as _traverse,
    extract_subgraph as _extract_subgraph,
)


def shortest_path(graph: IGraphAdapter, source: str, target: str) -> List[str]:
    """Return the shortest path between two nodes."""
    return _shortest_path(graph, source, target)


def traverse(
    graph: IGraphAdapter,
    start_node_id: str,
    depth: int,
    edge_label: Optional[str] = None,
) -> List[str]:
    """Traverse outward from ``start_node_id`` using the shared algorithm."""
    return _traverse(graph, start_node_id, depth, edge_label)


def extract_subgraph(
    graph: IGraphAdapter,
    start_node_id: str,
    depth: int,
    edge_label: Optional[str] = None,
    since_timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """Extract a subgraph using the shared algorithm."""
    return _extract_subgraph(graph, start_node_id, depth, edge_label, since_timestamp)


def constrained_path(
    graph: IGraphAdapter,
    source_id: str,
    target_id: str,
    max_depth: Optional[int] = None,
    edge_label: Optional[str] = None,
    since_timestamp: Optional[int] = None,
) -> List[str]:
    """Wrapper around :meth:`IGraphAdapter.constrained_path`."""
    return graph.constrained_path(
        source_id,
        target_id,
        max_depth=max_depth,
        edge_label=edge_label,
        since_timestamp=since_timestamp,
    )
