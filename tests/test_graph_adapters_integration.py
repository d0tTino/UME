import os
import pytest

from ume.postgres_graph import PostgresGraph
from ume.redis_graph_adapter import RedisGraphAdapter


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_postgres_graph_crud(postgres_service):
    graph = PostgresGraph(postgres_service["dsn"])
    graph.add_node("n1", {"v": 1})
    assert graph.get_node("n1") == {"v": 1}
    graph.update_node("n1", {"v": 2})
    assert graph.get_node("n1") == {"v": 2}
    graph.add_node("n2", {})
    graph.add_edge("n1", "n2", "R")
    assert ("n1", "n2", "R") in graph.get_all_edges()
    graph.delete_edge("n1", "n2", "R")
    assert graph.get_all_edges() == []
    graph.clear()
    graph.close()


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_redis_graph_crud(redis_service):
    graph = RedisGraphAdapter(redis_service["url"])
    graph.add_node("n1", {"v": 1})
    assert graph.get_node("n1") == {"v": 1}
    graph.update_node("n1", {"v": 2})
    assert graph.get_node("n1") == {"v": 2}
    graph.add_node("n2", {})
    graph.add_edge("n1", "n2", "R")
    assert ("n1", "n2", "R") in graph.get_all_edges()
    graph.delete_edge("n1", "n2", "R")
    assert graph.get_all_edges() == []
    graph.clear()
    graph.close()


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_redis_graph_scan_iter_large_dataset(redis_service, monkeypatch):
    graph = RedisGraphAdapter(redis_service["url"])
    for i in range(1000):
        graph.add_node(f"n{i}", {})

    def forbid_keys(*_: object, **__: object) -> None:
        raise AssertionError("keys() should not be called")

    monkeypatch.setattr(graph._client, "keys", forbid_keys)

    node_ids = graph.get_all_node_ids()
    assert len(node_ids) == 1000

    graph.clear()
    graph.close()
