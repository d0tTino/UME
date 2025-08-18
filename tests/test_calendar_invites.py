from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings
from ume.permissions_adapter import PermissionsGraphAdapter


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


def test_calendar_event_invites_create_edges_and_access(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Pre-create nodes for owner and invitees
    graph.add_node("owner", {"type": "User"})
    graph.add_node("invitee1", {"type": "User"})
    graph.add_node("invitee2", {"type": "User"})

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Planning",
            "start_time": start,
            "user_id": "owner",
            "invitee_ids": ["invitee1", "invitee2"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event_id = res.json()["id"]

    edges = graph.get_all_edges()
    for uid in ["invitee1", "invitee2"]:
        assert any(
            s == event_id and t == uid and lbl == "INVITES" for s, t, lbl, _ in edges
        )
        assert any(
            s == event_id and t == uid and lbl == "SHARED_WITH" for s, t, lbl, _ in edges
        )

        perm_graph = PermissionsGraphAdapter(graph, user_id=uid)
        assert event_id in perm_graph.get_nodes_by_user(uid)
