from fastapi.testclient import TestClient
from ume.api import app, configure_graph
from ume.graph import MockGraph
from ume.config import settings
from ume.plugins import alignment


def setup_module(_: object) -> None:
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: [{"q": q}]})()
    g = MockGraph()
    configure_graph(g)


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return str(res.json()["access_token"])


def test_reload_policies(monkeypatch):
    alignment._plugins.clear()
    client = TestClient(app)
    token = _token(client)
    res = client.post("/policies/reload", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(alignment.get_plugins()) > 0
