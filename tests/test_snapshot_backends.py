import pathlib
from typing import Optional
import pytest

from ume.snapshot import snapshot_graph_to_file, load_graph_into_existing
from ume.persistent_graph import PersistentGraph
from ume.postgres_graph import PostgresGraph
from ume.redis_graph_adapter import RedisGraphAdapter


@pytest.mark.parametrize(
    "backend,service",
    [
        ("sqlite", None),
        ("postgres", "postgres_service"),
        ("redis", "redis_service"),
    ],
)
def test_snapshot_roundtrip_all_backends(
    tmp_path: pathlib.Path,
    backend: str,
    service: Optional[str],
    request: pytest.FixtureRequest,
) -> None:
    if service:
        info = request.getfixturevalue(service)
        db_path = info["dsn"] if backend == "postgres" else info["url"]
    else:
        db_path = str(tmp_path / "graph.db")

    if backend == "sqlite":
        graph = PersistentGraph(db_path, check_same_thread=False)
    elif backend == "postgres":
        graph = PostgresGraph(db_path)
    else:
        graph = RedisGraphAdapter(db_path)

    graph.add_node("a", {"val": 1})
    graph.add_node("b", {"val": 2})
    graph.add_edge("a", "b", "L")

    snap = tmp_path / "snap.json"
    snapshot_graph_to_file(graph, snap)

    graph.clear()
    load_graph_into_existing(graph, snap)

    assert set(graph.get_all_node_ids()) == {"a", "b"}
    assert ("a", "b", "L", {}) in graph.get_all_edges()

    graph.clear()
    graph.close()
