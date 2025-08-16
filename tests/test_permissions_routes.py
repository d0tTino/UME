import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
        },
    )
    return res.json()["access_token"]


@pytest.fixture
def client_and_graph():
    graph = MockGraph()
    configure_graph(graph)
    return TestClient(app), graph


def _seed_graph(graph: MockGraph) -> None:
    # Subjects
    graph.add_node("user1", {"type": "User"})
    graph.add_node("group1", {"type": "UserGroup"})
    graph.add_node("other", {"type": "User"})

    # User-only nodes
    graph.add_node("u_viewer", {})
    graph.add_edge("u_viewer", "user1", "OWNED_BY", {"permission_level": "viewer"})
    graph.add_node("u_editor", {})
    graph.add_edge("u_editor", "user1", "OWNED_BY", {"permission_level": "editor"})

    # Group-only nodes
    graph.add_node("g_viewer", {})
    graph.add_edge("g_viewer", "group1", "SHARED_WITH", {"permission_level": "viewer"})
    graph.add_node("g_editor", {})
    graph.add_edge("g_editor", "group1", "SHARED_WITH", {"permission_level": "editor"})

    # Mixed node accessible to both
    graph.add_node("mixed", {})
    graph.add_edge("mixed", "user1", "OWNED_BY", {"permission_level": "viewer"})
    graph.add_edge("mixed", "group1", "SHARED_WITH", {"permission_level": "editor"})

    # Node unrelated to tested subjects
    graph.add_node("unrelated", {})
    graph.add_edge("unrelated", "other", "OWNED_BY", {"permission_level": "viewer"})


def test_get_nodes_by_user_filters_viewer_editor(client_and_graph):
    client, graph = client_and_graph
    _seed_graph(graph)
    token = _token(client)

    res = client.get(
        "/v1/nodes",
        params={"user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert set(res.json()["nodes"]) == {"u_viewer", "u_editor", "mixed"}


def test_get_nodes_shared_with_filters_viewer_editor(client_and_graph):
    client, graph = client_and_graph
    _seed_graph(graph)
    token = _token(client)

    res = client.get(
        "/v1/nodes/shared",
        params={"group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert set(res.json()["nodes"]) == {"g_viewer", "g_editor", "mixed"}
