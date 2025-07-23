from fastapi.testclient import TestClient

from ume.api import app
from ume.config import settings


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return str(res.json()["access_token"])


def test_add_and_view_dossier(monkeypatch):
    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "ProjectManager", raising=False)
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        "/dossier/add-project",
        json={"dossier_id": "d1", "project_id": "p1"},
        headers=headers,
    )
    assert res.status_code == 200
    assert "p1" in res.json()["projects"]

    res = client.get("/dossier/d1", headers=headers)
    assert res.status_code == 200
    assert res.json()["projects"] == ["p1"]


def test_add_project_forbidden(monkeypatch):
    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "Viewer", raising=False)
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        "/dossier/add-project",
        json={"dossier_id": "d2", "project_id": "p2"},
        headers=headers,
    )
    assert res.status_code == 403


def test_view_missing(monkeypatch):
    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "ProjectManager", raising=False)
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/dossier/unknown", headers=headers)
    assert res.status_code == 404

