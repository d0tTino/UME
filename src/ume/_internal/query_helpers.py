from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..graph_adapter import IGraphAdapter


def shortest_path(graph: IGraphAdapter, source: str, target: str) -> List[str]:
    """Wrapper around :meth:`IGraphAdapter.shortest_path`."""
    return graph.shortest_path(source, target)


def traverse(
    graph: IGraphAdapter,
    start_node_id: str,
    depth: int,
    edge_label: Optional[str] = None,
) -> List[str]:
    """Wrapper around :meth:`IGraphAdapter.traverse`."""
    return graph.traverse(start_node_id, depth, edge_label)


def extract_subgraph(
    graph: IGraphAdapter,
    start_node_id: str,
    depth: int,
    edge_label: Optional[str] = None,
    since_timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """Wrapper around :meth:`IGraphAdapter.extract_subgraph`."""
    return graph.extract_subgraph(start_node_id, depth, edge_label, since_timestamp)


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
