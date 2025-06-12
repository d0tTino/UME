import sys
from unittest.mock import Mock
from ume import graph_adapter as real_ga
sys.modules.setdefault("ume._internal.graph_adapter", real_ga)  # noqa: E402

from ume._internal import query_helpers as qh  # noqa: E402


def test_wrapper_methods_call_graph():
    graph = Mock()
    qh.shortest_path(graph, "a", "b")
    qh.traverse(graph, "a", 1, edge_label="L")
    qh.extract_subgraph(graph, "a", 2, edge_label=None, since_timestamp=5)
    qh.constrained_path(graph, "a", "b", max_depth=3, edge_label="L", since_timestamp=4)

    graph.shortest_path.assert_called_once_with("a", "b")
    graph.traverse.assert_called_once_with("a", 1, "L")
    graph.extract_subgraph.assert_called_once_with("a", 2, None, 5)
    graph.constrained_path.assert_called_once_with(
        "a",
        "b",
        max_depth=3,
        edge_label="L",
        since_timestamp=4,
    )

