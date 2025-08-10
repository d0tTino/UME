from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume.decisions_routes import router as decisions_router
from ume import MockGraph
from ume.config import settings

# Register decision routes for the test environment
app.include_router(decisions_router)


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


def test_calendar_event_permissions(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Pre-create user nodes so permission edges can be added
    graph.add_node("user1", {})
    graph.add_node("user2", {})
    graph.add_node("user3", {})

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Meeting",
            "start": start,
            "user_id": "user1",
            "invitee_ids": ["user2"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event_id = res.json()["id"]

    # Additional edges to satisfy PermissionsGraphAdapter's checks
    graph.add_edge(event_id, "user1", "editor")
    graph.add_edge(event_id, "user2", "viewer")

    # Owner sees the event
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert [e["id"] for e in res.json()] == [event_id]

    # Invitee sees the event
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert [e["id"] for e in res.json()] == [event_id]

    # Unrelated user cannot see the event
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user3"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []

    edges = graph.get_all_edges()
    assert (event_id, "user1", "HAS_PERMISSION", {"permission_level": "editor"}) in edges
    assert (event_id, "user2", "HAS_PERMISSION", {"permission_level": "viewer"}) in edges


def test_decision_flow(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Pre-create user node for permission edges
    graph.add_node("user1", {})

    res = client.post(
        "/v1/decisions",
        json={"query": "Choose option", "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={"description": "Option A", "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    action_id = res.json()["action_id"]

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["analysis"]["analysis_id"] == analysis_id
    assert [a["action_id"] for a in data["actions"]] == [action_id]

    assert graph.get_node(analysis_id)["query"] == "Choose option"
    assert graph.get_node(action_id)["description"] == "Option A"
    assert graph.find_connected_nodes(analysis_id, edge_label="CONSIDERS") == [action_id]
