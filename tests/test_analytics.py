from datetime import datetime, timedelta, timezone

from ume import MockGraph
from ume.analytics import (
    shortest_path,
    find_communities,
    temporal_node_counts,
    pagerank_centrality,
    betweenness_centrality,
    node_similarity,
)


def build_basic_graph():
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_node("c", {})
    g.add_edge("a", "b", "L")
    g.add_edge("b", "c", "L")
    g.add_edge("a", "c", "L")
    return g


def test_shortest_path():
    g = build_basic_graph()
    path = shortest_path(g, "a", "c")
    assert path == ["a", "c"]
    assert shortest_path(g, "c", "a") == []


def test_find_communities():
    g = build_basic_graph()
    g.add_node("x", {})
    g.add_node("y", {})
    g.add_edge("x", "y", "L")
    communities = find_communities(g)
    # Expect two communities of sizes 3 and 2
    sizes = sorted(len(c) for c in communities)
    assert sizes == [2, 3]


def test_temporal_node_counts():
    g = MockGraph()
    today = datetime.now(timezone.utc)
    g.add_node("n1", {"timestamp": int(today.timestamp())})
    g.add_node("n2", {"timestamp": int((today - timedelta(days=1)).timestamp())})
    g.add_node("n3", {"timestamp": int((today - timedelta(days=3)).timestamp())})
    counts = temporal_node_counts(g, 2)
    assert len(counts) == 2
    assert sum(counts.values()) == 2


def test_centrality_and_similarity():
    g = build_basic_graph()
    pr = pagerank_centrality(g)
    bc = betweenness_centrality(g)
    sims = node_similarity(g)
    assert set(pr) == {"a", "b", "c"}
    assert set(bc) == {"a", "b", "c"}
    assert all(len(t) == 3 for t in sims)
