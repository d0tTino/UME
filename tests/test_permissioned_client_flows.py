import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings
from ume.models.calendar import CalendarEventVisibility
from ume.models.financial_account import SCHEMA_VERSION as ACCOUNT_SCHEMA_VERSION
from ume.models.decision_analysis import SCHEMA_VERSION as ANALYSIS_SCHEMA_VERSION
from ume.models.proposed_action import SCHEMA_VERSION as ACTION_SCHEMA_VERSION


EDGE_VERSION = "3.0.0"


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


def test_calendar_events_require_layer_editor(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("owner", {})
    graph.add_node("viewer", {})
    graph.add_node("group1", {"type": "UserGroup", "members": ["owner", "viewer"]})

    layer_res = client.post(
        "/v1/calendar/layers",
        json={"layer_name": "Team", "color": "green", "user_id": "owner", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert layer_res.status_code == 200
    layer_id = layer_res.json()["layer_id"]

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Viewer attempt",
            "start_time": start,
            "user_id": "viewer",
            "group_id": "group1",
            "layer_ids": [layer_id],
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400

    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Owner event",
            "start_time": start,
            "user_id": "owner",
            "group_id": "group1",
            "layer_ids": [layer_id],
            "visibility": CalendarEventVisibility.PUBLIC_TO_GROUP.value,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event = res.json()

    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "viewer", "group_id": "group1", "layer_id": layer_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert [e["event_id"] for e in res.json()] == [event["event_id"]]

    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "outsider", "group_id": "group1", "layer_id": layer_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_financial_account_group_reads_require_membership(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("owner", {})
    graph.add_node("viewer", {})
    graph.add_node("outsider", {})
    graph.add_node("group1", {"type": "UserGroup", "members": ["owner", "viewer"]})

    res = client.post(
        "/v1/accounts",
        json={
            "account_type": "checking",
            "institution": "Bank",
            "balance": 10.0,
            "currency": "USD",
            "user_id": "owner",
            "group_id": "group1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    account_id = res.json()["id"]

    res = client.get(
        f"/v1/accounts/{account_id}",
        params={"user_id": "viewer", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["schema_version"] == ACCOUNT_SCHEMA_VERSION

    res = client.get(
        f"/v1/accounts/{account_id}",
        params={"user_id": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404

    res = client.get(
        f"/v1/accounts/{account_id}",
        params={"user_id": "outsider", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_decision_access_for_owner_and_group(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("owner", {})
    graph.add_node("member", {})
    graph.add_node("group1", {"type": "UserGroup", "members": ["owner", "member"]})

    res = client.post(
        "/v1/decisions",
        json={"query": "Pick", "user_id": "owner", "group_id": "group1", "group_permission_level": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={"description": "Choice", "user_id": "owner", "group_id": "group1", "group_permission_level": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    action_id = res.json()["action_id"]

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "owner"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["analysis"]["analysis_id"] == analysis_id
    assert data["analysis"]["schema_version"] == ANALYSIS_SCHEMA_VERSION
    assert [a["action_id"] for a in data["actions"]] == [action_id]
    assert data["actions"][0]["schema_version"] == ACTION_SCHEMA_VERSION

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "member"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "member", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["analysis"]["analysis_id"] == analysis_id

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "outsider", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
