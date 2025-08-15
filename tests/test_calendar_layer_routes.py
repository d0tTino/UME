from datetime import datetime, timezone

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


def test_create_calendar_layer(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)
    res = client.post(
        "/v1/calendar/layers",
        json={"layer_name": "Work", "color": "blue"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    layer_id = data["layer_id"]
    assert data == {"layer_id": layer_id, "layer_name": "Work", "color": "blue"}
    attrs = graph.get_node(layer_id)
    assert attrs == {"type": "CalendarLayer", "layer_name": "Work", "color": "blue"}


def test_event_layer_validation(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)
    graph.add_node("user1", {})
    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()
    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Meeting",
            "start": start,
            "user_id": "user1",
            "layer_ids": ["missing"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


def test_event_with_existing_layer(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)
    graph.add_node("user1", {})
    layer_res = client.post(
        "/v1/calendar/layers",
        json={"layer_name": "Work", "color": "blue"},
        headers={"Authorization": f"Bearer {token}"},
    )
    layer_id = layer_res.json()["layer_id"]
    graph.add_edge(
        layer_id, "user1", "SHARED_WITH", {"permission_level": "viewer"}
    )
    start_dt = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    start = start_dt.isoformat()
    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Meeting",
            "start": start,
            "user_id": "user1",
            "layer_ids": [layer_id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event_id = res.json()["id"]
    edges = graph.get_all_edges()
    assert any(
        s == event_id and t == layer_id and lbl == "TAGGED_AS" for s, t, lbl, _ in edges
    )
