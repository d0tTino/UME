from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume.graph import MockGraph
from ume.reliability import filter_low_confidence
from ume.config import settings


def _token(client: TestClient) -> str:
    res = client.post(
        "/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return res.json()["access_token"]


def test_filter_low_confidence() -> None:
    items = ["good", "123"]
    result = filter_low_confidence(items, 0.9)
    assert result == ["good"]


def test_shortest_path_low_confidence(monkeypatch) -> None:
    g = MockGraph()
    g.add_node("good", {})
    g.add_node("bad1", {})
    g.add_edge("good", "bad1", "L")
    configure_graph(g)

    monkeypatch.setattr(settings, "UME_RELIABILITY_THRESHOLD", 0.9)

    client = TestClient(app)
    token = _token(client)
    res = client.post(
        "/analytics/shortest_path",
        json={"source": "good", "target": "bad1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["path"] == ["good"]
