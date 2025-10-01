import os

import pytest

from ume.graph_schema import DEFAULT_SCHEMA
from ume.permissions_adapter import PermissionsGraphAdapter
from ume.postgres_graph import PostgresGraph


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("UME_DOCKER_TESTS"),
    reason="Docker tests disabled",
)
def test_get_nodes_by_user_returns_owned_resources(postgres_service):
    graph = PostgresGraph(postgres_service["dsn"])
    resource_id = "Document.pg_owned"
    shared_id = "Document.pg_shared"
    user_id = "User.pg_user"
    other_user = "User.pg_other"
    try:
        graph.add_node(resource_id, {"type": "Document"})
        graph.add_node(shared_id, {"type": "Document"})
        graph.add_node(user_id, {"type": "User"})
        graph.add_node(other_user, {"type": "User"})
        owned_schema = DEFAULT_SCHEMA.get_edge_version("OWNED_BY")
        shared_schema = DEFAULT_SCHEMA.get_edge_version("SHARED_WITH")
        graph.add_edge(
            resource_id,
            user_id,
            "OWNED_BY",
            {"permission_level": "editor"},
            schema_version=owned_schema,
        )
        graph.add_edge(
            shared_id,
            other_user,
            "OWNED_BY",
            {"permission_level": "editor"},
            schema_version=owned_schema,
        )
        graph.add_edge(
            shared_id,
            user_id,
            "SHARED_WITH",
            {"permission_level": "viewer"},
            schema_version=shared_schema,
        )

        permissions_graph = PermissionsGraphAdapter(graph, user_id=user_id)
        assert set(permissions_graph.get_nodes_by_user(user_id)) == {
            resource_id,
            shared_id,
        }

        edges = graph.get_all_edges()
        assert (
            resource_id,
            user_id,
            "OWNED_BY",
            {"permission_level": "editor", "schema_version": owned_schema},
        ) in edges
        assert (
            shared_id,
            user_id,
            "SHARED_WITH",
            {"permission_level": "viewer", "schema_version": shared_schema},
        ) in edges
    finally:
        graph.clear()
        graph.close()
