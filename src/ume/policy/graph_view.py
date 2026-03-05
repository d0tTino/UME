"""Helpers for building backend-agnostic graph read views for policy input."""

from __future__ import annotations

from typing import Any

from ..event import Event
from ..graph_adapter import IGraphAdapter


def build_graph_read_view(
    graph: IGraphAdapter,
    *,
    event: Event,
    max_snapshot_nodes: int,
    neighborhood_depth: int,
    max_neighborhood_nodes: int,
) -> dict[str, Any]:
    node_ids = graph.get_all_node_ids()
    if len(node_ids) <= max_snapshot_nodes:
        snapshot = graph.dump()
        return {
            "mode": "snapshot",
            "node_count": len(node_ids),
            "nodes": snapshot.get("nodes", {}),
            "edges": snapshot.get("edges", []),
            "truncated": False,
        }

    center_ids = [node_id for node_id in [event.node_id, event.target_node_id] if node_id]
    if not center_ids:
        payload_node = event.payload.get("node_id")
        payload_target = event.payload.get("target_node_id")
        center_ids = [node_id for node_id in [payload_node, payload_target] if isinstance(node_id, str)]

    nodes: dict[str, Any] = {}
    edges: list[Any] = []
    for center in center_ids[:2]:
        subgraph = graph.extract_subgraph(center, depth=neighborhood_depth)
        for node_id, attributes in subgraph.get("nodes", {}).items():
            if len(nodes) >= max_neighborhood_nodes:
                break
            nodes[node_id] = attributes
        if len(nodes) >= max_neighborhood_nodes:
            break
        edges.extend(subgraph.get("edges", []))

    return {
        "mode": "neighborhood",
        "node_count": len(nodes),
        "nodes": nodes,
        "edges": edges,
        "center_node_ids": center_ids,
        "depth": neighborhood_depth,
        "truncated": len(nodes) >= max_neighborhood_nodes,
    }
