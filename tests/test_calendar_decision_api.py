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

    start_dt = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    end_dt = datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc)
    start = start_dt.isoformat()
    end = end_dt.isoformat()
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Meeting",
            "start": start,
            "end": end,
            "description": "Discuss project",
            "is_all_day": True,
            "location": "Conference Room",
            "status": "confirmed",
            "rrule": "FREQ=DAILY",
            "visibility": "public",
            "user_id": "user1",
            "invitee_ids": ["user2"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event_data = res.json()
    event_id = event_data["id"]
    assert event_data == {
        "id": event_id,
        "title": "Meeting",
        "start": start_ts,
        "end": end_ts,
        "description": "Discuss project",
        "is_all_day": True,
        "location": "Conference Room",
        "status": "confirmed",
        "rrule": "FREQ=DAILY",
        "visibility": "public",
    }

    # Owner sees the event with all properties
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == [event_data]

    # Invitee sees the event with all properties
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == [event_data]

    # Unrelated user cannot see the event
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user3"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []

    attrs = graph.get_node(event_id)
    assert attrs["title"] == "Meeting"
    assert attrs["start"] == start_ts
    assert attrs["end"] == end_ts
    assert attrs["description"] == "Discuss project"
    assert attrs["is_all_day"] is True
    assert attrs["location"] == "Conference Room"
    assert attrs["status"] == "confirmed"
    assert attrs["rrule"] == "FREQ=DAILY"
    assert attrs["visibility"] == "public"

    edges = graph.get_all_edges()
    assert (event_id, "user1", "OWNED_BY", {"permission_level": "editor"}) in edges
    assert (event_id, "user2", "SHARED_WITH", {"permission_level": "viewer"}) in edges


def test_calendar_event_group_permissions(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Pre-create user and group nodes
    graph.add_node("user1", {})
    graph.add_node("user2", {})
    graph.add_node("group1", {})

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={"title": "Standup", "start": start, "user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event_data = res.json()
    event_id = event_data["id"]

    # Unrelated user without group access cannot see the event
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []

    # Group-scoped retrieval returns the event
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user2", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == [event_data]

    edges = graph.get_all_edges()
    assert (event_id, "group1", "SHARED_WITH", {"permission_level": "viewer"}) in edges


def test_calendar_event_unauthorized_access(client_and_graph) -> None:
    client, _ = client_and_graph

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={"title": "Meeting", "start": start, "user_id": "user1"},
    )
    assert res.status_code == 401

    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user1"},
    )
    assert res.status_code == 401


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

    from unittest.mock import patch

    def patched_has_permission_edge(self, node_id, subject, perm):
        for src, tgt, lbl, attrs in self._adapter.get_all_edges():
            if src == node_id and tgt == subject and lbl in {"OWNED_BY", "SHARED_WITH", "HAS_PERMISSION"}:
                perm_level = None
                if isinstance(attrs, dict):
                    perm_level = attrs.get("permission_level")
                else:
                    perm_level = attrs
                if perm_level == perm:
                    return True
        return False

    with patch(
        "ume.permissions_adapter.PermissionsGraphAdapter._has_permission_edge",
        patched_has_permission_edge,
    ):
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
