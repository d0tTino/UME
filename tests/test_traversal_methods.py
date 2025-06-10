from ume import MockGraph


def build_graph():
    g = MockGraph()
    g.add_node("a", {"timestamp": 1})
    g.add_node("b", {"timestamp": 2})
    g.add_node("c", {"timestamp": 3})
    g.add_node("d", {"timestamp": 4})
    g.add_edge("a", "b", "L")
    g.add_edge("b", "c", "L")
    g.add_edge("a", "d", "L")
    return g


def test_shortest_path_method():
    g = build_graph()
    assert g.shortest_path("a", "c") == ["a", "b", "c"]
    assert g.shortest_path("c", "a") == []


def test_traverse_method():
    g = build_graph()
    result = g.traverse("a", depth=2)
    assert set(result) == {"b", "d", "c"}


def test_extract_subgraph():
    g = build_graph()
    sub = g.extract_subgraph("a", depth=1)
    assert set(sub["nodes"].keys()) == {"a", "b", "d"}
    assert len(sub["edges"]) == 2
    recent = g.extract_subgraph("a", depth=2, since_timestamp=3)
    assert set(recent["nodes"].keys()) == {"c", "d"}
