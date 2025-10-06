import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


USER_ID = "User.redactor"


def _params(user_id: str = USER_ID) -> dict[str, str]:
    return {"user_id": user_id}


@pytest.fixture
def client_and_graph():
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_edge("a", "b", "L")
    g.add_node(USER_ID, {"type": "User"})
    g.add_edge(
        "a",
        USER_ID,
        "OWNED_BY",
        {"permission_level": "editor"},
    )
    g.add_edge(
        "b",
        USER_ID,
        "OWNED_BY",
        {"permission_level": "editor"},
    )
    configure_graph(g)
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    orig_role = settings.UME_OAUTH_ROLE
    settings.UME_OAUTH_ROLE = ""
    try:
        yield TestClient(app), g
    finally:
        settings.UME_OAUTH_ROLE = orig_role


def test_redact_node_endpoint(client_and_graph):
    client, g = client_and_graph
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.post(
        "/redact/node/a",
        headers={"Authorization": f"Bearer {token}"},
        params=_params(),
    )
    assert res.status_code == 200
    assert g.get_node("a") is None


def test_redact_edge_endpoint(client_and_graph):
    client, g = client_and_graph
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.post(
        "/redact/edge",
        json={"source": "a", "target": "b", "label": "L"},
        headers={"Authorization": f"Bearer {token}"},
        params=_params(),
    )
    assert res.status_code == 200
    remaining = g.get_all_edges()
    assert all(lbl != "L" for _, _, lbl, _ in remaining)
