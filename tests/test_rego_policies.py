from pathlib import Path
from typing import Any
from fastapi.testclient import TestClient
from ume.api import app, configure_graph
from ume.graph import MockGraph
from ume.config import settings


def setup_module(_: object) -> None:
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: [{"q": q}]})()
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_edge("a", "b", "L")
    configure_graph(g)


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return str(res.json()["access_token"])



def test_policy_upload_and_delete(tmp_path: Path, monkeypatch: Any) -> None:
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
    assert (tmp_path / "test.rego").exists()

    res = client.get("/policies", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert "test.rego" in res.json()["policies"]

    res = client.delete(
        "/policies/test.rego",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert not (tmp_path / "test.rego").exists()


def test_policy_routes_require_auth(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr("ume.api.POLICY_DIR", tmp_path)
    client = TestClient(app)
    content = b"package test\nallow = true"
    res_post = client.post(
        "/policies/test.rego",
        files={"file": ("test.rego", content)},
    )
    assert res_post.status_code == 401

    res_list = client.get("/policies")
    assert res_list.status_code == 401

    res_delete = client.delete("/policies/test.rego")
    assert res_delete.status_code == 401
