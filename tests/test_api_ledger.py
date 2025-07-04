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

