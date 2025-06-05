"""Graph analytics utilities built on top of :class:`~ume.graph_adapter.IGraphAdapter`."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Set

import networkx as nx

from .graph_adapter import IGraphAdapter


def _to_networkx(graph: IGraphAdapter) -> nx.DiGraph:
    """Convert an ``IGraphAdapter`` implementation into a ``networkx`` graph."""
    g = nx.DiGraph()
    for node_id in graph.get_all_node_ids():
        attrs = graph.get_node(node_id) or {}
        g.add_node(node_id, **attrs)
    for src, tgt, label in graph.get_all_edges():
        g.add_edge(src, tgt, label=label)
    return g


def shortest_path(graph: IGraphAdapter, src: str, dst: str) -> List[str]:
    """Return the shortest directed path from ``src`` to ``dst``.

    If no path exists an empty list is returned.
    """
    g = _to_networkx(graph)
    try:
        return nx.shortest_path(g, src, dst)
    except nx.NetworkXNoPath:
        return []
    except nx.NodeNotFound:
        return []


def find_communities(graph: IGraphAdapter) -> List[Set[str]]:
    """Detect communities using a greedy modularity algorithm."""
    g = _to_networkx(graph).to_undirected()
    communities = nx.algorithms.community.greedy_modularity_communities(g)
    return [set(c) for c in communities]


def temporal_node_counts(graph: IGraphAdapter, past_n_days: int) -> Dict[str, int]:
    """Count nodes with a ``timestamp`` attribute over the last ``past_n_days``.

    The timestamp attribute is assumed to be a Unix epoch integer.
    The return value maps ISO date strings (YYYY-MM-DD) to counts.
    """
    cutoff = datetime.utcnow() - timedelta(days=past_n_days)
    buckets: Dict[str, int] = {}
    for node_id in graph.get_all_node_ids():
        data = graph.get_node(node_id) or {}
        ts = data.get("timestamp")
        if isinstance(ts, (int, float)):
            dt = datetime.utcfromtimestamp(int(ts))
            if dt >= cutoff:
                key = dt.date().isoformat()
                buckets[key] = buckets.get(key, 0) + 1
    return buckets
