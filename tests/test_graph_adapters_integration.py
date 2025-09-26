import os
import pytest

from ume.arango_graph import ArangoGraph
from ume.postgres_graph import PostgresGraph
from ume.redis_graph_adapter import RedisGraphAdapter
from ume.neo4j_graph import Neo4jGraph
from ume.permissions_adapter import PermissionsGraphAdapter
from ume.graph_schema import DEFAULT_SCHEMA
import redis


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
    assert ("n1", "n2", "R", {}) in graph.get_all_edges()
    graph.add_node("n3", {})
    graph.add_edge(
        "n1",
        "n3",
        "SHARED_WITH",
        {"permission_level": "viewer"},
        schema_version="3.0.0",
    )
    edges = graph.get_all_edges()
    assert (
        "n1",
        "n3",
        "SHARED_WITH",
        {"permission_level": "viewer", "schema_version": "3.0.0"},
    ) in edges
    graph.delete_edge("n1", "n2", "R")
    graph.delete_edge("n1", "n3", "SHARED_WITH")
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
    assert ("n1", "n2", "R", {}) in graph.get_all_edges()
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


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_redis_clear_preserves_unrelated_keys(redis_service):
    client = redis.from_url(redis_service["url"])
    client.set("unrelated", "value")

    graph = RedisGraphAdapter(redis_service["url"])
    graph.add_node("n1", {})
    graph.clear()

    assert client.get("unrelated") == b"value"
    assert list(client.scan_iter(f"{RedisGraphAdapter.NODE_PREFIX}*")) == []
    assert list(client.scan_iter(f"{RedisGraphAdapter.EDGE_PREFIX}*")) == []
    assert not client.exists(RedisGraphAdapter.REDACTED_NODES_KEY)
    assert not client.exists(RedisGraphAdapter.REDACTED_EDGES_KEY)
    client.close()


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_permissions_adapter_with_redis(redis_service):
    graph = RedisGraphAdapter(redis_service["url"])
    resource_id = "Document.redis_doc"
    user_id = "User.redis_owner"
    schema_version = DEFAULT_SCHEMA.get_edge_version("OWNED_BY")
    try:
        graph.add_node(resource_id, {"type": "Document"})
        graph.add_node(user_id, {"type": "User"})
        graph.add_edge(
            resource_id,
            user_id,
            "OWNED_BY",
            {"permission_level": "editor"},
            schema_version=schema_version,
        )

        edges = graph.get_all_edges()
        assert any(
            s == resource_id
            and t == user_id
            and lbl == "OWNED_BY"
            and edge_attrs.get("permission_level") == "editor"
            and edge_attrs.get("schema_version") == schema_version
            for s, t, lbl, edge_attrs in edges
        )

        permissions_graph = PermissionsGraphAdapter(graph, user_id=user_id)
        assert resource_id in permissions_graph.get_nodes_by_user(user_id)
    finally:
        graph.clear()
        graph.close()


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_permissions_adapter_with_arango(arango_service):
    try:
        graph = ArangoGraph(
            arango_service["url"],
            arango_service["user"],
            arango_service["password"],
        )
    except ImportError:  # pragma: no cover - optional dependency missing
        pytest.skip("python-arango not installed")

    resource_id = "Document.arango_doc"
    user_id = "User.arango_owner"
    schema_version = DEFAULT_SCHEMA.get_edge_version("OWNED_BY")
    try:
        graph.add_node(resource_id, {"type": "Document"})
        graph.add_node(user_id, {"type": "User"})
        graph.add_edge(
            resource_id,
            user_id,
            "OWNED_BY",
            {"permission_level": "editor"},
            schema_version=schema_version,
        )


        edges = graph.get_all_edges()
        assert any(
            s == resource_id
            and t == user_id
            and lbl == "OWNED_BY"
            and edge_attrs.get("permission_level") == "editor"
            and edge_attrs.get("schema_version") == schema_version

            for s, t, lbl, edge_attrs in edges
        )

        permissions_graph = PermissionsGraphAdapter(graph, user_id=user_id)
        assert resource_id in permissions_graph.get_nodes_by_user(user_id)

    finally:
        graph.clear()
        graph.close()

