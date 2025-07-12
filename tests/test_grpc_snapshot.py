import pathlib
from ume.snapshot import snapshot_graph_to_file, load_graph_into_existing
from ume.graph import MockGraph


def test_snapshot_roundtrip(tmp_path: pathlib.Path) -> None:
    graph = MockGraph()
    graph.add_node("a", {"val": 1})
    path = tmp_path / "snap.json"
    snapshot_graph_to_file(graph, path)
    assert path.is_file()
    graph.clear()
    load_graph_into_existing(graph, path)
    assert graph.get_node("a") == {"val": 1}

