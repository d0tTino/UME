"""Graph analytics utilities built on top of :class:`~ume.graph_adapter.IGraphAdapter`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set

from collections import deque
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

    This implementation relies on ``graph.find_connected_nodes`` so role-based
    access checks are enforced by :class:`~ume.rbac_adapter.RoleBasedGraphAdapter`.
    If no path exists an empty list is returned.
    """
    visited: Dict[str, str | None] = {src: None}
    queue: deque[str] = deque([src])
    while queue:
        current = queue.popleft()
        if current == dst:
            break
        for neighbor in graph.find_connected_nodes(current):
            if neighbor not in visited:
                visited[neighbor] = current
                queue.append(neighbor)

    if dst not in visited:
        return []

    path = [dst]
    while visited[path[-1]] is not None:
        prev = visited[path[-1]]
        assert prev is not None
        path.append(prev)
    path.reverse()
    return path


def find_communities(graph: IGraphAdapter) -> List[Set[str]]:
    """Detect communities in the graph."""
    db_method = getattr(graph, "community_detection", None)
    if callable(db_method):
        try:
            return db_method()
        except NotImplementedError:
            pass

    g = _to_networkx(graph).to_undirected()
    communities = nx.algorithms.community.greedy_modularity_communities(g)
    return [set(c) for c in communities]


def pagerank_centrality(graph: IGraphAdapter) -> Dict[str, float]:
    """Return PageRank centrality scores for all nodes."""
    db_method = getattr(graph, "pagerank_centrality", None)
    if callable(db_method):
        try:
            return db_method()
        except NotImplementedError:
            pass

    g = _to_networkx(graph)
    return nx.pagerank(g)


def betweenness_centrality(graph: IGraphAdapter) -> Dict[str, float]:
    """Return betweenness centrality scores for all nodes."""
    db_method = getattr(graph, "betweenness_centrality", None)
    if callable(db_method):
        try:
            return db_method()
        except NotImplementedError:
            pass

    g = _to_networkx(graph).to_undirected()
    return nx.betweenness_centrality(g)


def node_similarity(graph: IGraphAdapter) -> List[tuple[str, str, float]]:
    """Return node similarity scores as `(source, target, score)` tuples."""
    db_method = getattr(graph, "node_similarity", None)
    if callable(db_method):
        try:
            return db_method()
        except NotImplementedError:
            pass

    g = _to_networkx(graph).to_undirected()
    return [(u, v, p) for u, v, p in nx.jaccard_coefficient(g)]


def graph_similarity(graph1: IGraphAdapter, graph2: IGraphAdapter) -> float:
    """Return a Jaccard similarity score between two graphs."""
    db_method = getattr(graph1, "graph_similarity", None)
    if callable(db_method) and type(graph1) is type(graph2):
        try:
            return db_method(graph2)
        except NotImplementedError:
            pass

    edges1 = set(graph1.get_all_edges())
    edges2 = set(graph2.get_all_edges())
    if not edges1 and not edges2:
        return 1.0
    return len(edges1 & edges2) / len(edges1 | edges2)


def temporal_node_counts(graph: IGraphAdapter, past_n_days: int) -> Dict[str, int]:
    """Count nodes with a ``timestamp`` attribute over the last ``past_n_days``.

    The timestamp attribute is assumed to be a Unix epoch integer.
    The return value maps ISO date strings (YYYY-MM-DD) to counts.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=past_n_days)
    buckets: Dict[str, int] = {}
    for node_id in graph.get_all_node_ids():
        data = graph.get_node(node_id) or {}
        ts = data.get("timestamp")
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(int(ts), timezone.utc)
            if dt >= cutoff:
                key = dt.date().isoformat()
                buckets[key] = buckets.get(key, 0) + 1
    return buckets


def temporal_community_detection(
    graph: IGraphAdapter, past_n_days: int
) -> List[Set[str]]:
    """Detect communities considering nodes within ``past_n_days``."""
    db_method = getattr(graph, "temporal_community_detection", None)
    if callable(db_method):
        try:
            return db_method(past_n_days)
        except NotImplementedError:
            pass

    cutoff = datetime.now(timezone.utc) - timedelta(days=past_n_days)
    g = _to_networkx(graph).to_undirected()
    nodes = [
        n
        for n, data in g.nodes(data=True)
        if isinstance(data.get("timestamp"), (int, float))
        and datetime.fromtimestamp(int(data["timestamp"]), timezone.utc) >= cutoff
    ]
    sub = g.subgraph(nodes).copy()
    if sub.number_of_nodes() == 0:
        return []
    communities = nx.algorithms.community.greedy_modularity_communities(sub)
    return [set(c) for c in communities]


def time_varying_centrality(graph: IGraphAdapter, past_n_days: int) -> Dict[str, float]:
    """Compute PageRank centrality over nodes seen in ``past_n_days``."""
    db_method = getattr(graph, "time_varying_centrality", None)
    if callable(db_method):
        try:
            return db_method(past_n_days)
        except NotImplementedError:
            pass

    cutoff = datetime.now(timezone.utc) - timedelta(days=past_n_days)
    g = _to_networkx(graph)
    nodes = [
        n
        for n, data in g.nodes(data=True)
        if isinstance(data.get("timestamp"), (int, float))
        and datetime.fromtimestamp(int(data["timestamp"]), timezone.utc) >= cutoff
    ]
    sub = g.subgraph(nodes).copy()
    if sub.number_of_nodes() == 0:
        return {}
    return nx.pagerank(sub)
