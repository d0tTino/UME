from fastapi.testclient import TestClient

from ume.api import app
from ume.config import settings
from ume.dossier import (
    Dossier,
    add_project,
    add_reflection,
    add_skill,
    add_value,
    add_memory,
    list_projects,
    list_skills,
    list_memories,
)


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return str(res.json()["access_token"])


def test_add_and_view_dossier(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "ProjectManager", raising=False)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
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


def test_add_project_forbidden(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "Viewer", raising=False)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        "/dossier/add-project",
        json={"dossier_id": "d2", "project_id": "p2"},
        headers=headers,
    )
    assert res.status_code == 403


def test_view_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "ProjectManager", raising=False)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/dossier/unknown", headers=headers)
    assert res.status_code == 404


def test_dossier_persists_after_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "ProjectManager", raising=False)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        "/dossier/add-project",
        json={"dossier_id": "d3", "project_id": "p3"},
        headers=headers,
    )
    assert res.status_code == 200

    reloaded = Dossier.load(tmp_path / "d3")
    assert "p3" in list_projects(reloaded)


def test_reflection_and_pref_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "ProjectManager", raising=False)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/dossier/add-reflection",
        json={"dossier_id": "d4", "text": "thinking"},
        headers=headers,
    )
    assert res.status_code == 200

    res = client.post(
        "/dossier/add-memory",
        json={"dossier_id": "d4", "text": "fact"},
        headers=headers,
    )
    assert res.status_code == 200

    res = client.post(
        "/dossier/set-pref",
        json={"dossier_id": "d4", "key": "theme", "value": "dark"},
        headers=headers,
    )
    assert res.status_code == 200

    res = client.post(
        "/dossier/add-project",
        json={"dossier_id": "d4", "project_id": "p4"},
        headers=headers,
    )
    assert res.status_code == 200

    dossier = Dossier.load(tmp_path / "d4")
    assert dossier.reflections[0]["text"] == "thinking"
    assert "id" in dossier.reflections[0]
    assert dossier.preferences["theme"] == "dark"

    res = client.post(
        "/dossier/add-value",
        json={"dossier_id": "d4", "value": "honesty"},
        headers=headers,
    )
    assert res.status_code == 200

    res = client.post(
        "/dossier/add-skill",
        json={"dossier_id": "d4", "skill": "python"},
        headers=headers,
    )
    assert res.status_code == 200

    res = client.get("/dossier/skills/d4", headers=headers)
    assert res.status_code == 200
    assert res.json()["skills"] == ["python"]

    res = client.get("/dossier/projects/d4", headers=headers)
    assert res.status_code == 200
    assert res.json()["projects"] == ["p4"]

    res = client.get("/dossier/reflections/d4", headers=headers)
    assert res.status_code == 200
    assert res.json()["reflections"] == ["thinking"]

    res = client.get("/dossier/memories/d4", headers=headers)
    assert res.status_code == 200
    assert res.json()["memories"] == ["fact"]

    res = client.get("/dossier/values/d4", headers=headers)
    assert res.status_code == 200
    assert res.json()["values"] == ["honesty"]

    dossier = Dossier.load(tmp_path / "d4")
    assert dossier.values == ["honesty"]
    assert list_skills(dossier) == ["python"]
    assert list_memories(dossier) == ["fact"]


def test_reflection_and_pref_forbidden(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "Viewer", raising=False)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/dossier/add-reflection",
        json={"dossier_id": "d5", "text": "idea"},
        headers=headers,
    )
    assert res.status_code == 403

    res = client.post(
        "/dossier/set-pref",
        json={"dossier_id": "d5", "key": "foo", "value": "bar"},
        headers=headers,
    )
    assert res.status_code == 403

    res = client.post(
        "/dossier/add-value",
        json={"dossier_id": "d5", "value": "honesty"},
        headers=headers,
    )
    assert res.status_code == 403

    res = client.post(
        "/dossier/add-skill",
        json={"dossier_id": "d5", "skill": "python"},
        headers=headers,
    )
    assert res.status_code == 403

    res = client.post(
        "/dossier/add-memory",
        json={"dossier_id": "d5", "text": "idea"},
        headers=headers,
    )
    assert res.status_code == 403


def test_projects_viewer_forbidden(tmp_path, monkeypatch):
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    dossier = Dossier.init_dossier(tmp_path / "d6")
    add_project(dossier, "p6")
    dossier.shareable_projects = False
    dossier.save()

    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "Viewer", raising=False)
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/dossier/projects/d6", headers=headers)
    assert res.status_code == 403


def test_projects_viewer_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    dossier = Dossier.init_dossier(tmp_path / "d7")
    add_project(dossier, "p7")
    dossier.shareable_projects = True
    dossier.save()

    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "Viewer", raising=False)
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/dossier/projects/d7", headers=headers)
    assert res.status_code == 200
    assert res.json()["projects"] == ["p7"]


def test_reflections_viewer_allowed_by_role(tmp_path, monkeypatch):
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    dossier = Dossier.init_dossier(tmp_path / "d8")
    add_reflection(dossier, "r8")
    dossier.shareable_reflections = False
    dossier.save()

    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "Viewer", raising=False)
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/dossier/reflections/d8", headers=headers)
    assert res.status_code == 200
    assert res.json()["reflections"] == ["r8"]


def test_reflections_viewer_allowed_shareable(tmp_path, monkeypatch):
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    dossier = Dossier.init_dossier(tmp_path / "d9")
    add_reflection(dossier, "r9")
    dossier.shareable_reflections = True
    dossier.save()

    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "Viewer", raising=False)
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/dossier/reflections/d9", headers=headers)
    assert res.status_code == 200
    assert res.json()["reflections"] == ["r9"]


def test_skills_values_memories_viewer_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    dossier = Dossier.init_dossier(tmp_path / "d10")
    add_skill(dossier, "python")
    add_value(dossier, "honesty")
    add_memory(dossier, "fact")
    dossier.shareable_reflections = False
    dossier.save()

    monkeypatch.setattr(settings, "UME_OAUTH_ROLE", "Viewer", raising=False)
    client = TestClient(app)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/dossier/skills/d10", headers=headers)
    assert res.status_code == 200
    assert res.json()["skills"] == ["python"]

    res = client.get("/dossier/values/d10", headers=headers)
    assert res.status_code == 200
    assert res.json()["values"] == ["honesty"]

    res = client.get("/dossier/memories/d10", headers=headers)
    assert res.status_code == 200
    assert res.json()["memories"] == ["fact"]

