import pytest
pytest.importorskip("fastapi")
import os
from pathlib import Path
from fastapi.testclient import TestClient
from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return str(res.json()["access_token"])


def setup_module(_: object) -> None:
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()


def test_snapshot_roundtrip(tmp_path: Path) -> None:
    g = MockGraph()
    g.add_node("a", {"x": 1})
    g.add_node("b", {"y": 2})
    g.add_edge("a", "b", "L")
    configure_graph(g)

    client = TestClient(app)
    token = _token(client)
    snap = tmp_path / "snap.json"

    res_save = client.post(
        "/snapshot/save",
        json={"path": str(snap)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_save.status_code == 200
    assert snap.is_file()

    g.clear()
    assert g.get_all_node_ids() == []

    res_load = client.post(
        "/snapshot/load",
        json={"path": str(snap)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_load.status_code == 200
    assert set(g.get_all_node_ids()) == {"a", "b"}
    assert ("a", "b", "L") in g.get_all_edges()


def test_snapshot_requires_analytics_role(tmp_path: Path) -> None:
    g = MockGraph()
    configure_graph(g)

    client = TestClient(app)
    orig_role = settings.UME_OAUTH_ROLE
    os.environ["UME_OAUTH_ROLE"] = "AutoDev"
    settings.UME_OAUTH_ROLE = "AutoDev"
    token = _token(client)
    os.environ["UME_OAUTH_ROLE"] = orig_role or ""
    settings.UME_OAUTH_ROLE = orig_role

    res = client.post(
        "/snapshot/save",
        json={"path": str(tmp_path / "s.json")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
