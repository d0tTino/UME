from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return res.json()["access_token"]


@pytest.fixture
def client_and_graph():
    graph = MockGraph()
    configure_graph(graph)
    return TestClient(app), graph


def test_end_before_start_rejected(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)
    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()
    end = datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc).isoformat()
    res = client.post(
        "/v1/calendar/events",
        json={"title": "Meeting", "start_time": start, "end_time": end, "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


def test_valid_event_creation(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)
    start_dt = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    end_dt = datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc)
    res = client.post(
        "/v1/calendar/events",
        json={
            "title": "Meeting",
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "user_id": "user1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event_id = res.json()["id"]
    attrs = graph.get_node(event_id)
    assert attrs["start_time"] == int(start_dt.timestamp())
    assert attrs["end_time"] == int(end_dt.timestamp())
