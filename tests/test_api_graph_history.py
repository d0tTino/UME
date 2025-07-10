import pytest
from fastapi.testclient import TestClient

from ume.api import app
from ume.config import settings
from ume.event_ledger import EventLedger


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return res.json()["access_token"]


def test_graph_history_offset(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    ledger.append(
        0,
        {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "a", "payload": {"node_id": "a"}},
    )
    ledger.append(
        1,
        {"event_type": "CREATE_NODE", "timestamp": 2, "node_id": "b", "payload": {"node_id": "b"}},
    )
    monkeypatch.setattr("ume.ledger_routes.event_ledger", ledger)

    client = TestClient(app)
    token = _token(client)
    res = client.get(
        "/graph/history",
        headers={"Authorization": f"Bearer {token}"},
        params={"offset": 0},
    )
    assert res.status_code == 200
    data = res.json()
    assert set(data["nodes"].keys()) == {"a"}


def test_graph_history_timestamp(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        "/graph/history",
        headers={"Authorization": f"Bearer {token}"},
        params={"timestamp": 1},
    )
    assert res.status_code == 200
    data = res.json()
    assert set(data["nodes"].keys()) == {"c"}

