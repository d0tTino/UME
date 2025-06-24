from fastapi.testclient import TestClient
from ume.api import app, configure_graph
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ume import MockGraph
from ume.config import settings
import time
import pytest


def setup_module(_: object) -> None:
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_edge("a", "b", "L")
    configure_graph(g)


def _get(client: TestClient):
    return client.get(
        "/analytics/path/stream",
        params={"source": "a", "target": "b"},
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )


def test_streaming_path() -> None:
    with TestClient(app) as client:
        res = _get(client)
        assert res.status_code == 200
        data = [line for line in res.iter_lines() if line.startswith("data:")]
        assert data == ["data: a", "data: b"]


@pytest.mark.skip("Redis not available for rate limit test")
def test_rate_limit() -> None:
    with TestClient(app) as client:
        _get(client)
        _get(client)
        res = _get(client)
        assert res.status_code == 429


@pytest.mark.skip("Redis not available for backpressure test")
def test_backpressure() -> None:
    with TestClient(app) as client:
        res = _get(client)
        assert res.status_code == 200
        it = (line for line in res.iter_lines() if line)
        first = next(it)
        assert first == "data: a"
        time.sleep(0.05)
        second = next(it)
        assert second == "data: b"
