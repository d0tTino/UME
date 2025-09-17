from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


def _token(client: TestClient) -> str:
    response = client.post(
        "/auth/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
        },
    )
    return response.json()["access_token"]


@pytest.fixture
def client_and_graph() -> tuple[TestClient, MockGraph]:
    graph = MockGraph()
    configure_graph(graph)
    return TestClient(app), graph


def test_event_creation_rolls_back_on_validation_failure(
    client_and_graph: tuple[TestClient, MockGraph], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, graph = client_and_graph
    token = _token(client)

    event_uuid = uuid.UUID("00000000-0000-0000-0000-000000000123")
    monkeypatch.setattr("ume.models.calendar.uuid.uuid4", lambda: event_uuid)

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc)

    response = client.post(
        "/v1/calendar/events",
        json={
            "title": "Team Sync",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "user_id": "user1",
            "layer_ids": ["missing-layer"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid layer_id: missing-layer"

    event_id = str(event_uuid)
    assert not graph.node_exists(event_id)
    assert graph.get_node(event_id) is None
