from fastapi.testclient import TestClient
from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings
from ume.dossier import Dossier


def _client(role: str):
    configure_graph(MockGraph())
    object.__setattr__(settings, "UME_API_TOKEN", "tkn")
    object.__setattr__(settings, "UME_API_ROLE", role)
    return TestClient(app)


def test_snapshot_permission(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UME_DOSSIER_PATH", str(tmp_path), raising=False)
    Dossier.init_dossier(tmp_path / "d1")

    client = _client("ProjectManager")
    res = client.post("/dossier/snapshot", json={"dossier_id": "d1"}, headers={"Authorization": "Bearer tkn"})
    assert res.status_code == 403

    client = _client("TelemetryAdmin")
    res = client.post("/dossier/snapshot", json={"dossier_id": "d1"}, headers={"Authorization": "Bearer tkn"})
    assert res.status_code == 200
    object.__setattr__(settings, "UME_API_ROLE", "")


def test_add_activity_permission(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UME_DOSSIER_PATH", str(tmp_path), raising=False)
    Dossier.init_dossier(tmp_path / "d2")

    client = _client("Viewer")
    res = client.post(
        "/dossier/add-activity",
        json={"dossier_id": "d2", "payload": {"a": 1}},
        headers={"Authorization": "Bearer tkn"},
    )
    assert res.status_code == 403

    client = _client("TelemetryAdmin")
    res = client.post(
        "/dossier/add-activity",
        json={"dossier_id": "d2", "payload": {"a": 1}},
        headers={"Authorization": "Bearer tkn"},
    )
    assert res.status_code == 200
    object.__setattr__(settings, "UME_API_ROLE", "")
