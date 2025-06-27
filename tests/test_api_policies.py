from pathlib import Path
from typing import Any
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume.graph import MockGraph
from ume.config import settings



def setup_module(_: object) -> None:
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: [{"q": q}]})()
    g = MockGraph()
    configure_graph(g)


def _token(client: TestClient) -> str:
    res = client.post(
        "/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return str(res.json()["access_token"])


def test_upload_download_delete(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr("ume.api.POLICY_DIR", tmp_path)
    client = TestClient(app)
    token = _token(client)

    content = b"package test\nallow = true"
    res = client.post(
        "/policies/test.rego",
        files={"file": ("test.rego", content)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert (tmp_path / "test.rego").read_bytes() == content

    res_get = client.get(
        "/policies/test.rego",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_get.status_code == 200
    assert res_get.text == content.decode()

    res_del = client.delete(
        "/policies/test.rego",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_del.status_code == 200
    assert not (tmp_path / "test.rego").exists()


def test_invalid_policy_paths(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr("ume.api.POLICY_DIR", tmp_path)
    client = TestClient(app)
    token = _token(client)
    auth = {"Authorization": f"Bearer {token}"}

    bad_paths = ["%2E%2E/bad.rego", "%2Fabs.rego"]
    for path in bad_paths:
        res = client.post(
            f"/policies/{path}",
            files={"file": ("bad.rego", b"p=1")},
            headers=auth,
        )
        assert res.status_code == 400

        res = client.get(f"/policies/{path}", headers=auth)
        assert res.status_code == 400

        res = client.delete(f"/policies/{path}", headers=auth)
        assert res.status_code == 400


def test_delete_missing_policy(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr("ume.api.POLICY_DIR", tmp_path)
    client = TestClient(app)
    token = _token(client)

    res = client.delete(
        "/policies/missing.rego",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
