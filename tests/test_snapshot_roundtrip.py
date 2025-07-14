import json
import pathlib
import pytest

from ume import (
    PersistentGraph,
    snapshot_graph_to_file,
    load_graph_from_file,
    SnapshotError,
)


def _build_sample_graph() -> PersistentGraph:
    graph = PersistentGraph(":memory:")
    graph.add_node("a", {"foo": "bar"})
    graph.add_node("b", {"baz": 1})
    graph.add_edge("a", "b", "KNOWS")
    return graph


def test_snapshot_load_roundtrip(tmp_path: pathlib.Path) -> None:
    graph = _build_sample_graph()
    first_snapshot = tmp_path / "snap1.json"
    snapshot_graph_to_file(graph, first_snapshot)

    loaded = load_graph_from_file(first_snapshot)
    assert loaded.dump() == graph.dump()

    second_snapshot = tmp_path / "snap2.json"
    snapshot_graph_to_file(loaded, second_snapshot)

    with open(first_snapshot, "r", encoding="utf-8") as f1, open(
        second_snapshot, "r", encoding="utf-8"
    ) as f2:
        assert json.load(f1) == json.load(f2)


def test_load_graph_from_file_duplicate_nodes(tmp_path: pathlib.Path) -> None:
    snapshot_file = tmp_path / "dup_nodes.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        f.write('{"nodes": {"n1": {}, "n1": {}}}')

    with pytest.raises(SnapshotError, match="Duplicate key 'n1'"):
        load_graph_from_file(snapshot_file)


def test_load_graph_from_file_malformed_json(tmp_path: pathlib.Path) -> None:
    snapshot_file = tmp_path / "bad.json"
    snapshot_file.write_text("{'nodes': [}", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_graph_from_file(snapshot_file)
