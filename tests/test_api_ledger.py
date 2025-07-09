import os

import pytest
from fastapi.testclient import TestClient
from ume.api import app
from ume.config import settings
from ume.event_ledger import EventLedger


def _token(client):
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return res.json()["access_token"]


def test_list_ledger_events(tmp_path, monkeypatch):
    path = str(tmp_path / "ledger.db")
    ledger = EventLedger(path)
    ledger.append(0, {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {"node_id": "n1"}})
    ledger.append(1, {"event_type": "CREATE_NODE", "timestamp": 2, "node_id": "n2", "payload": {"node_id": "n2"}})
    monkeypatch.setattr("ume.ledger_routes.event_ledger", ledger)

    client = TestClient(app)
    token = _token(client)
    res = client.get("/ledger/events", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["offset"] == 0
    assert data[1]["offset"] == 1


def test_list_ledger_events_range_and_limit(tmp_path, monkeypatch):
    path = str(tmp_path / "ledger.db")
    ledger = EventLedger(path)
    for i in range(5):
        ledger.append(
            i,
            {
                "event_type": "CREATE_NODE",
                "timestamp": i,
                "node_id": f"n{i}",
                "payload": {"node_id": f"n{i}"},
            },
        )

    monkeypatch.setattr("ume.ledger_routes.event_ledger", ledger)

    client = TestClient(app)
    token = _token(client)

    res = client.get(
        "/ledger/events",
        headers={"Authorization": f"Bearer {token}"},
        params={"start": 1, "end": 3},
    )
    assert res.status_code == 200
    data = res.json()
    assert [e["offset"] for e in data] == [1, 2, 3]

    res = client.get(
        "/ledger/events",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 2},
    )
    assert res.status_code == 200
    data = res.json()
    assert [e["offset"] for e in data] == [0, 1]


def test_replay_endpoint_sqlite(tmp_path, monkeypatch):
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    ledger.append(0, {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "a", "payload": {"node_id": "a"}})
    ledger.append(1, {"event_type": "CREATE_NODE", "timestamp": 2, "node_id": "b", "payload": {"node_id": "b"}})
    monkeypatch.setattr("ume.ledger_routes.event_ledger", ledger)

    client = TestClient(app)
    token = _token(client)
    res = client.get(
        "/ledger/replay",
        headers={"Authorization": f"Bearer {token}"},
        params={"end_offset": 0},
    )
    assert res.status_code == 200
    data = res.json()
    assert set(data["nodes"].keys()) == {"a"}


def test_replay_endpoint_sqlite_timestamp(tmp_path, monkeypatch):
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    ledger.append(
        0,
        {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "c", "payload": {"node_id": "c"}},
    )
    ledger.append(
        1,
        {"event_type": "CREATE_NODE", "timestamp": 3, "node_id": "d", "payload": {"node_id": "d"}},
    )
    monkeypatch.setattr("ume.ledger_routes.event_ledger", ledger)

    client = TestClient(app)
    token = _token(client)
    res = client.get(
        "/ledger/replay",
        headers={"Authorization": f"Bearer {token}"},
        params={"end_timestamp": 1},
    )
    assert res.status_code == 200
    data = res.json()
    assert set(data["nodes"].keys()) == {"c"}


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_replay_endpoint_postgres(tmp_path, monkeypatch, postgres_service):
    path = str(tmp_path / "ledger.db")
    ledger = EventLedger(path)
    ledger.append(0, {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "x", "payload": {"node_id": "x"}})
    ledger.append(1, {"event_type": "CREATE_NODE", "timestamp": 2, "node_id": "y", "payload": {"node_id": "y"}})
    monkeypatch.setattr("ume.ledger_routes.event_ledger", ledger)

    from ume.postgres_graph import PostgresGraph
    from ume.api_deps import configure_graph

    graph = PostgresGraph(postgres_service["dsn"])
    configure_graph(graph)

    client = TestClient(app)
    token = _token(client)
    res = client.get(
        "/ledger/replay",
        headers={"Authorization": f"Bearer {token}"},
        params={"end_offset": 1},
    )
    assert res.status_code == 200
    data = res.json()
    assert set(data["nodes"].keys()) == {"x", "y"}


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_replay_endpoint_postgres_timestamp(tmp_path, monkeypatch, postgres_service):
    path = str(tmp_path / "ledger.db")
    ledger = EventLedger(path)
    ledger.append(
        0,
        {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "p", "payload": {"node_id": "p"}},
    )
    ledger.append(
        1,
        {"event_type": "CREATE_NODE", "timestamp": 5, "node_id": "q", "payload": {"node_id": "q"}},
    )
    monkeypatch.setattr("ume.ledger_routes.event_ledger", ledger)

    from ume.postgres_graph import PostgresGraph
    from ume.api_deps import configure_graph

    graph = PostgresGraph(postgres_service["dsn"])
    configure_graph(graph)

    client = TestClient(app)
    token = _token(client)
    res = client.get(
        "/ledger/replay",
        headers={"Authorization": f"Bearer {token}"},
        params={"end_timestamp": 1},
    )
    assert res.status_code == 200
    data = res.json()
    assert set(data["nodes"].keys()) == {"p"}

