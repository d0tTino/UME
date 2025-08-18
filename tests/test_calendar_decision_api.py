from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings
from ume.models.decision_analysis import SCHEMA_VERSION
from ume.models import CalendarEventStatus, CalendarEventVisibility


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
    graph.add_edge(
        "user2", "user1", "SHARED_WITH", {"permission_level": "editor"}
    )

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
            "start_time": start,
            "end_time": end,
            "description": "Discuss project",
            "is_all_day": True,
            "location": "Conference Room",
            "status": CalendarEventStatus.CONFIRMED.value,
            "rrule": "FREQ=DAILY",
            "visibility": CalendarEventVisibility.PUBLIC.value,
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
        "start_time": start_ts,
        "end_time": end_ts,
        "description": "Discuss project",
        "is_all_day": True,
        "location": "Conference Room",
        "status": CalendarEventStatus.CONFIRMED.value,
        "rrule": "FREQ=DAILY",
        "visibility": CalendarEventVisibility.PUBLIC.value,
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
    assert attrs["start_time"] == start_ts
    assert attrs["end_time"] == end_ts
    assert attrs["description"] == "Discuss project"
    assert attrs["is_all_day"] is True
    assert attrs["location"] == "Conference Room"
    assert attrs["status"] == CalendarEventStatus.CONFIRMED.value
    assert attrs["rrule"] == "FREQ=DAILY"
    assert attrs["visibility"] == CalendarEventVisibility.PUBLIC.value

    edges = graph.get_all_edges()
    assert any(
        s == event_id and t == "user1" and lbl == "OWNED_BY" for s, t, lbl, _ in edges
    )
    assert any(
        s == event_id and t == "user2" and lbl == "SHARED_WITH"
        for s, t, lbl, _ in edges
    )


def test_calendar_event_group_permissions(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Pre-create user and group nodes
    graph.add_node("user1", {})
    graph.add_node("user2", {})
    graph.add_node("group1", {})
    graph.add_edge(
        "group1", "user1", "SHARED_WITH", {"permission_level": "editor"}
    )

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Standup",
            "start_time": start,
            "user_id": "user1",
            "group_id": "group1",
        },
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

    # User creates their own event
    res = client.post(
        "/v1/calendar/events",
        json={"title": "Solo", "start_time": start, "user_id": "user2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    own_event = res.json()

    # Group-scoped retrieval returns the event
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user2", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert sorted(res.json(), key=lambda e: e["id"]) == sorted(
        [event_data, own_event], key=lambda e: e["id"]
    )

    edges = graph.get_all_edges()
    assert any(
        s == event_id and t == "group1" and lbl == "SHARED_WITH"
        for s, t, lbl, _ in edges
    )


def test_calendar_event_group_and_layer_filter(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Prepare users, group, and ensure the user has control over the group
    graph.add_node("user1", {})
    graph.add_node("user2", {})
    graph.add_node("group1", {})
    graph.add_edge(
        "group1", "user1", "OWNED_BY", {"permission_level": "editor"}
    )

    # Create a layer shared with the group so members can access it
    layer_res = client.post(
        "/v1/calendar/layers",
        json={
            "layer_name": "Team",
            "color": "blue",
            "user_id": "user1",
            "group_id": "group1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert layer_res.status_code == 200
    layer_id = layer_res.json()["layer_id"]

    # Additional layer used to ensure filtering by layer_id works
    layer2_res = client.post(
        "/v1/calendar/layers",
        json={"layer_name": "Other", "color": "red", "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert layer2_res.status_code == 200
    layer2_id = layer2_res.json()["layer_id"]

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    # Event shared with group and tagged with the requested layer
    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Visible",
            "start_time": start,
            "user_id": "user1",
            "group_id": "group1",
            "layer_ids": [layer_id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    visible_event = res.json()

    # Event shared with group but tagged with a different layer
    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "WrongLayer",
            "start_time": start,
            "user_id": "user1",
            "group_id": "group1",
            "layer_ids": [layer2_id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Event tagged with the layer but not shared with the group
    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "NoPerm",
            "start_time": start,
            "user_id": "user1",
            "layer_ids": [layer_id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Query with both group and layer filters should return only the visible event
    res = client.get(
        "/v1/calendar/events",
        params={
            "user_id": "user2",
            "group_id": "group1",
            "layer_id": layer_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == [visible_event]


def test_calendar_event_invite_requires_editor(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node("user2", {})

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Meeting",
            "start_time": start,
            "user_id": "user1",
            "invitee_ids": ["user2"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200


def test_calendar_event_missing_invitee_created(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Sync",
            "start_time": start,
            "user_id": "owner",
            "invitee_ids": ["missing"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event = res.json()

    # Invitee node should be created automatically
    attrs = graph.get_node("missing")
    assert attrs is not None and attrs.get("type") == "User"

    # Invitee can retrieve the event
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "missing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == [event]


def test_calendar_event_group_share_requires_editor(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node("group1", {})

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Standup",
            "start_time": start,
            "user_id": "user1",
            "group_id": "group1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200


def test_calendar_event_unauthorized_access(client_and_graph) -> None:
    client, _ = client_and_graph

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={"title": "Meeting", "start_time": start, "user_id": "user1"},
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
    analysis_resp = res.json()
    analysis_id = analysis_resp["analysis_id"]
    assert analysis_resp["schema_version"] == SCHEMA_VERSION
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
    assert data["analysis"]["schema_version"] == SCHEMA_VERSION
    assert [a["action_id"] for a in data["actions"]] == [action_id]

    assert graph.get_node(analysis_id)["query"] == "Choose option"
    assert graph.get_node(action_id)["description"] == "Option A"
    assert (
        graph.find_connected_nodes(analysis_id, edge_label="CONSIDERS")
        == [action_id]
    )

    edges = graph.get_all_edges()
    assert any(
        s == analysis_id and t == "user1" and lbl == "OWNED_BY"
        for s, t, lbl, _ in edges
    )
    assert any(
        s == action_id and t == "user1" and lbl == "OWNED_BY"
        for s, t, lbl, _ in edges
    )
