import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
import pytest
pytest.importorskip("fastapi")
from ume.api import app
from ume.config import settings


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return res.json()["access_token"]


def test_consent_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UME_CONSENT_LEDGER_PATH", str(tmp_path / "ledger.db"))
    from ume.consent_ledger import ConsentLedger
    ledger = ConsentLedger(str(tmp_path / "ledger.db"))
    monkeypatch.setattr("ume.api.consent_ledger", ledger)

    client = TestClient(app)
    token = _token(client)
    auth = {"Authorization": f"Bearer {token}"}

    res = client.get("/consent", headers=auth)
    assert res.status_code == 200
    assert res.json() == []

    res = client.post("/consent", json={"user_id": "u1", "scope": "s1"}, headers=auth)
    assert res.status_code == 200

    res = client.get("/consent", headers=auth)
    data = res.json()
    assert len(data) == 1
    assert data[0]["user_id"] == "u1"
    assert data[0]["scope"] == "s1"

    res = client.delete("/consent", params={"user_id": "u1", "scope": "s1"}, headers=auth)
    assert res.status_code == 200
    assert client.get("/consent", headers=auth).json() == []
