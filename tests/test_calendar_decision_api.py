from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.permissions_adapter import PermissionsGraphAdapter
from ume.rbac_adapter import AccessDeniedError
from ume.config import settings
from ume.models.decision_analysis import SCHEMA_VERSION
from ume.models.proposed_action import SCHEMA_VERSION as ACTION_SCHEMA_VERSION
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
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
            "user_id": "user1",
            "invitee_ids": ["user2"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event_data = res.json()
    event_id = event_data["event_id"]
    assert event_data == {
        "event_id": event_id,
        "title": "Meeting",
        "start_time": start_ts,
        "end_time": end_ts,
        "description": "Discuss project",
        "is_all_day": True,
        "location": "Conference Room",
        "status": CalendarEventStatus.CONFIRMED.value,
        "rrule": "FREQ=DAILY",
        "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
        "schema_version": SCHEMA_VERSION,
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
    assert attrs["type"] == "CalendarEvent"
    assert attrs["event_id"] == event_id
    assert attrs["title"] == "Meeting"
    assert attrs["start_time"] == start_ts
    assert attrs["end_time"] == end_ts
    assert attrs["description"] == "Discuss project"
    assert attrs["is_all_day"] is True
    assert attrs["location"] == "Conference Room"
    assert attrs["status"] == CalendarEventStatus.CONFIRMED.value
    assert attrs["rrule"] == "FREQ=DAILY"
    assert attrs["visibility"] == CalendarEventVisibility.PUBLIC_TO_GROUP.value
    assert attrs["schema_version"] == SCHEMA_VERSION

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
    graph.add_node("group1", {"members": ["user1", "user2"]})
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
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event_data = res.json()
    event_id = event_data["event_id"]

    # Unrelated user without group access cannot see the event
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []

    # User creates their own private event
    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Solo",
            "start_time": start,
            "user_id": "user2",
            "visibility": CalendarEventVisibility.PRIVATE.value,
        },
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
    assert res.json() == [event_data]

    # Event shared with the group granting editor rights
    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Planning",
            "start_time": start,
            "user_id": "user1",
            "group_id": "group1",
            "group_permission_level": "editor",
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    editor_event = res.json()

    # Group-scoped retrieval now returns both events
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user2", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    returned_ids = {evt["event_id"] for evt in res.json()}
    assert returned_ids == {event_data["event_id"], editor_event["event_id"]}

    edges = graph.get_all_edges()
    assert any(
        s == event_id and t == "group1" and lbl == "SHARED_WITH"
        and attrs.get("permission_level") == "viewer"
        for s, t, lbl, attrs in edges
    )
    assert not any(
        s == own_event["event_id"] and t == "group1" and lbl == "SHARED_WITH"
        for s, t, lbl, _ in edges
    )
    assert any(
        s == editor_event["event_id"]
        and t == "group1"
        and lbl == "SHARED_WITH"
        and attrs.get("permission_level") == "editor"
        for s, t, lbl, attrs in edges
    )


def test_calendar_event_group_membership_required(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Create users and a group with a single member
    graph.add_node("user1", {})
    graph.add_node("user2", {})
    graph.add_node("group1", {"members": ["user1"]})

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    # Non-member cannot create an event for the group
    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Meet",
            "start_time": start,
            "user_id": "user2",
            "group_id": "group1",
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403

    # Member creates an event
    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Meet",
            "start_time": start,
            "user_id": "user1",
            "group_id": "group1",
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Non-member cannot list events scoped to the group
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user2", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_calendar_event_missing_group_returns_404(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})

    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user1", "group_id": "missing"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 404
    assert res.json() == {"detail": "Group not found"}


def test_calendar_event_group_and_layer_filter(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Prepare users, group, and ensure the user has control over the group
    graph.add_node("user1", {})
    graph.add_node("user2", {})
    graph.add_node("group1", {"members": ["user1", "user2"]})
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
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
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
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    wrong_layer_event = res.json()

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
    no_group_event = res.json()

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

    edges = graph.get_all_edges()
    assert any(
        s == visible_event["event_id"] and t == "group1" and lbl == "SHARED_WITH"
        for s, t, lbl, _ in edges
    )
    assert any(
        s == visible_event["event_id"] and t == layer_id and lbl == "TAGGED_AS"
        for s, t, lbl, _ in edges
    )
    assert any(
        s == wrong_layer_event["event_id"] and t == "group1" and lbl == "SHARED_WITH"
        for s, t, lbl, _ in edges
    )
    assert any(
        s == wrong_layer_event["event_id"] and t == layer2_id and lbl == "TAGGED_AS"
        for s, t, lbl, _ in edges
    )
    assert not any(
        s == wrong_layer_event["event_id"] and t == layer_id and lbl == "TAGGED_AS"
        for s, t, lbl, _ in edges
    )
    assert any(
        s == no_group_event["event_id"] and t == layer_id and lbl == "TAGGED_AS"
        for s, t, lbl, _ in edges
    )
    assert not any(
        s == no_group_event["event_id"] and t == "group1" and lbl == "SHARED_WITH"
        for s, t, lbl, _ in edges
    )


def test_calendar_event_group_query_includes_owned_private(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node("user2", {})
    graph.add_node("group1", {"members": ["user1", "user2"]})
    graph.add_edge(
        "group1", "user1", "OWNED_BY", {"permission_level": "editor"}
    )

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    private_res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Private",
            "start_time": start,
            "user_id": "user1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert private_res.status_code == 200
    private_event = private_res.json()

    public_res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Group Public",
            "start_time": start,
            "user_id": "user1",
            "group_id": "group1",
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert public_res.status_code == 200
    public_event = public_res.json()

    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert {event["event_id"] for event in res.json()} == {
        private_event["event_id"],
        public_event["event_id"],
    }

    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user2", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert {event["event_id"] for event in res.json()} == {
        public_event["event_id"]
    }


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


def test_create_event_rollback(monkeypatch, client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    original_add_edge = PermissionsGraphAdapter.add_edge
    created_event_ids: list[str] = []

    def fail_on_invites(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs=None,
        schema_version=None,
    ):
        if label == "INVITES":
            created_event_ids.append(source_node_id)
            raise AccessDeniedError("Invite creation failed")
        return original_add_edge(
            self, source_node_id, target_node_id, label, attrs, schema_version
        )

    monkeypatch.setattr(PermissionsGraphAdapter, "add_edge", fail_on_invites)

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Rollback",
            "start_time": start,
            "user_id": "owner",
            "invitee_ids": ["invitee"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 403
    assert res.json() == {"detail": "Invite creation failed"}

    assert created_event_ids
    event_id = created_event_ids[0]
    assert event_id not in graph.get_all_node_ids()
    assert graph.get_node(event_id) is None

    visible_events = [
        nid
        for nid in graph.get_all_node_ids()
        if (graph.get_node(nid) or {}).get("type") == "CalendarEvent"
    ]
    assert visible_events == []
    remaining_edges = graph.get_all_edges()
    assert all(event_id not in (s, t) for s, t, *_ in remaining_edges)


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
    event_id = res.json()["event_id"]
    invitee_attrs = graph.get_node("missing")
    assert invitee_attrs is not None
    assert invitee_attrs["type"] == "User"
    assert invitee_attrs["user_id"] == "missing"
    edges = graph.get_all_edges()
    assert any(
        s == event_id and t == "missing" and lbl == "INVITES"
        for s, t, lbl, _ in edges
    )
    assert any(
        s == event_id and t == "missing" and lbl == "SHARED_WITH"
        for s, t, lbl, _ in edges
    )


def test_calendar_event_group_share_requires_editor(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node("group1", {"members": ["user1"]})

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Standup",
            "start_time": start,
            "user_id": "user1",
            "group_id": "group1",
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200


def test_calendar_event_private_group_rejected(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node("group1", {"members": ["user1"]})

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Hidden",
            "start_time": start,
            "user_id": "user1",
            "group_id": "group1",
            "visibility": CalendarEventVisibility.PRIVATE.value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


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


def test_calendar_events_since_returns_only_future(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Pre-create user node for permission edges
    graph.add_node("user1", {})

    past = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    since = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    future = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    # Create a past event
    res = client.post(
        "/v1/calendar/events",
        json={"title": "Past", "start_time": past.isoformat(), "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Create an event at the since timestamp
    res = client.post(
        "/v1/calendar/events",
        json={"title": "At", "start_time": since.isoformat(), "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Create a future event
    res = client.post(
        "/v1/calendar/events",
        json={"title": "Future", "start_time": future.isoformat(), "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    future_event = res.json()

    # Query events since the middle timestamp
    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "user1", "since": int(since.timestamp())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == [future_event]


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
    action = res.json()
    action_id = action["action_id"]
    assert action["schema_version"] == ACTION_SCHEMA_VERSION

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
    assert data["actions"][0]["schema_version"] == ACTION_SCHEMA_VERSION

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
