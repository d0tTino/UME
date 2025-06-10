from __future__ import annotations

from typing import Any, Dict, List, Optional

from .graph_adapter import IGraphAdapter


def constrained_path(
    graph: IGraphAdapter,
    source: str,
    target: str,
    max_depth: Optional[int] = None,
    edge_label: Optional[str] = None,
    since_timestamp: Optional[int] = None,
) -> List[str]:
    """Find a path between two nodes honoring optional constraints."""
    return graph.constrained_path(
        source, target, max_depth, edge_label, since_timestamp
    )


def subgraph(
    graph: IGraphAdapter,
    start_node_id: str,
    depth: int,
    edge_label: Optional[str] = None,
    since_timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """Convenience wrapper around :meth:`IGraphAdapter.extract_subgraph`."""
    return graph.extract_subgraph(start_node_id, depth, edge_label, since_timestamp)


def neighbors(
    graph: IGraphAdapter, node_id: str, edge_label: Optional[str] = None
) -> List[str]:
    """Return connected nodes using :meth:`IGraphAdapter.find_connected_nodes`."""
    return graph.find_connected_nodes(node_id, edge_label)
