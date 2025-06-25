from unittest.mock import Mock
from ume import graph_adapter as real_ga, MockGraph

from ume._internal import query_helpers as qh  # noqa: E402


def test_import_igraphadapter_consistency() -> None:
    assert qh.IGraphAdapter is real_ga.IGraphAdapter


def build_graph() -> MockGraph:
    g = MockGraph()
    g.add_node("a", {"timestamp": 1})
    g.add_node("b", {"timestamp": 2})
    g.add_node("c", {"timestamp": 3})
    g.add_node("d", {"timestamp": 4})
    g.add_edge("a", "b", "L")
    g.add_edge("b", "c", "L")
    g.add_edge("a", "d", "L")
    return g


def test_wrapper_methods_execute_algorithms() -> None:
    g = build_graph()
    assert qh.shortest_path(g, "a", "c") == ["a", "b", "c"]
    assert set(qh.traverse(g, "a", 2)) == {"b", "d", "c"}
    sub = qh.extract_subgraph(g, "a", 1)
    assert set(sub["nodes"].keys()) == {"a", "b", "d"}

    mock = Mock()
    qh.constrained_path(mock, "x", "y", max_depth=3)
    mock.constrained_path.assert_called_once_with(
        "x", "y", max_depth=3, edge_label=None, since_timestamp=None
    )
