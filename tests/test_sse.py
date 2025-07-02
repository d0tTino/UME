from fastapi.testclient import TestClient
from starlette.responses import Response
from typing import cast
from ume.api import app, configure_graph
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ume import MockGraph
from ume.config import settings
from sse_starlette.sse import AppStatus
import anyio
import time
import pytest



def setup_module(_: object) -> None:
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_edge("a", "b", "L")
    object.__setattr__(settings, "UME_API_TOKEN", "")
    configure_graph(g)
    AppStatus.should_exit = False
    AppStatus.should_exit_event = anyio.Event()


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return cast(str, res.json()["access_token"])


def _get(client: TestClient) -> Response:
    return client.stream(
        "GET",
        "/analytics/path/stream",
        params={"source": "a", "target": "b"},
        headers={"Authorization": f"Bearer {_token(client)}"},
    )


@pytest.mark.skip(reason="Flaky in CI")  # type: ignore[misc]

def test_streaming_path() -> None:
    with TestClient(app) as client:
        with _get(client) as res:
            assert res.status_code == 200
            data = [line for line in res.iter_lines() if line.startswith("data:")]
        assert data == ["data: a", "data: b"]


@pytest.mark.skip("Redis not available for rate limit test")  # type: ignore[misc]
def test_rate_limit() -> None:
    with TestClient(app) as client:
        _get(client)
        _get(client)
        res = _get(client)
        assert res.status_code == 429


@pytest.mark.skip("Redis not available for backpressure test")  # type: ignore[misc]
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


def teardown_module(_: object) -> None:
    AppStatus.should_exit_event = None
    AppStatus.should_exit = False
