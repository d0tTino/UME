from unittest.mock import Mock
import importlib.util
from pathlib import Path
import sys

module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "graph_queries.py"
spec = importlib.util.spec_from_file_location("ume.graph_queries", module_path)
assert spec and spec.loader
gq = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gq
spec.loader.exec_module(gq)


def test_graph_query_wrappers():
    m = Mock()
    gq.constrained_path(m, "a", "b", max_depth=2, edge_label="L", since_timestamp=5)
    m.constrained_path.assert_called_once_with("a", "b", 2, "L", 5)

    gq.subgraph(m, "s", 3, edge_label="E", since_timestamp=1)
    m.extract_subgraph.assert_called_once_with("s", 3, "E", 1)

    gq.neighbors(m, "n", edge_label="X")
    m.find_connected_nodes.assert_called_once_with("n", "X")

