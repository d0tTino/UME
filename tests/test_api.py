# ruff: noqa: E402
from fastapi.testclient import TestClient
import pytest
from typing import Any
import time

faiss = pytest.importorskip("faiss")
if not hasattr(faiss, "IndexFlatL2"):
    pytest.skip("faiss is missing required functionality", allow_module_level=True)

from ume.api import app, configure_graph, configure_vector_store
from ume.vector_store import VectorStore
from ume import MockGraph
from ume.config import settings
from pytest import MonkeyPatch, LogCaptureFixture


def setup_module(_: object) -> None:
    # configure app state for tests
    object.__setattr__(settings, "UME_API_TOKEN", "secret-token")
    app.state.query_engine = type(
        "QE", (), {"execute_cypher": lambda self, q: [{"q": q}]}
    )()
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_edge("a", "b", "L")
    configure_graph(g)


def _token(client: TestClient) -> str:
    res = client.post(
        "/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
        },
    )
    token = res.json()["access_token"]
    assert isinstance(token, str)
    return token


def test_run_query_authorized() -> None:
    client = TestClient(app)
    token = _token(client)
    res = client.get(
        "/query",
        params={"cypher": "MATCH (n) RETURN n"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == [{"q": "MATCH (n) RETURN n"}]


def test_run_query_unauthorized() -> None:
    client = TestClient(app)
    res = client.get("/query", params={"cypher": "MATCH (n)"})
    assert res.status_code == 401


def test_shortest_path_endpoint() -> None:
    client = TestClient(app)
    token = _token(client)
    payload = {"source": "a", "target": "b"}
    res = client.post(
        "/analytics/shortest_path",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == {"path": ["a", "b"]}


def test_constrained_path_endpoint() -> None:
    client = TestClient(app)
    token = _token(client)
    payload = {"source": "a", "target": "b", "max_depth": 1}
    res = client.post(
        "/analytics/path",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == {"path": ["a", "b"]}


def test_subgraph_endpoint() -> None:
    client = TestClient(app)
    token = _token(client)
    payload = {"start": "a", "depth": 1}
    res = client.post(
        "/analytics/subgraph",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert set(res.json()["nodes"].keys()) == {"a", "b"}


def test_token_header_whitespace_and_case() -> None:
    client = TestClient(app)
    token = _token(client)
    res = client.get(
        "/query",
        params={"cypher": "MATCH (n)"},
        headers={"Authorization": f"  bearer {token}  "},
    )
    assert res.status_code == 401


def test_expired_token(monkeypatch: MonkeyPatch) -> None:
    client = TestClient(app)
    token = _token(client)
    # force expiry in the past
    from ume import api as api_mod

    role, _ = api_mod.TOKENS[token]
    api_mod.TOKENS[token] = (role, time.time() - 1)
    res = client.get(
        "/query",
        params={"cypher": "MATCH (n)"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 401


def test_malformed_authorization_header() -> None:
    client = TestClient(app)
    res = client.get(
        "/query",
        params={"cypher": "MATCH (n)"},
        headers={"Authorization": "Token bad"},
    )
    assert res.status_code == 401


def test_metrics_endpoint_authorized() -> None:
    client = TestClient(app)
    token = _token(client)
    res = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_metrics_summary() -> None:
    configure_vector_store(VectorStore(dim=2, use_gpu=False))
    client = TestClient(app)
    token = _token(client)
    client.get(
        "/query",
        params={"cypher": "MATCH (n) RETURN n"},
        headers={"Authorization": f"Bearer {token}"},
    )
    res = client.get(
        "/metrics/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "vector_index_size" in data
    assert "average_request_latency" in data


def test_dashboard_endpoints() -> None:
    configure_vector_store(VectorStore(dim=2, use_gpu=False))
    client = TestClient(app)
    token = _token(client)
    res_stats = client.get(
        "/dashboard/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert "node_count" in stats
    assert "edge_count" in stats
    assert "vector_index_size" in stats
    res_events = client.get(
        "/dashboard/recent_events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_events.status_code == 200
    assert isinstance(res_events.json(), list)


@pytest.mark.parametrize(
    "method,path,body,params",
    [
        ("post", "/analytics/shortest_path", {"source": "a", "target": "b"}, None),
        ("post", "/analytics/path", {"source": "a", "target": "b"}, None),
        ("post", "/analytics/subgraph", {"start": "a", "depth": 1}, None),
        ("post", "/redact/node/a", None, None),
        ("post", "/redact/edge", {"source": "a", "target": "b", "label": "L"}, None),
        ("post", "/nodes", {"id": "x"}, None),
        ("patch", "/nodes/a", {"attributes": {}}, None),
        ("delete", "/nodes/a", None, None),
        ("post", "/edges", {"source": "a", "target": "b", "label": "L"}, None),
        ("delete", "/edges/a/b/L", None, None),
        (
            "get",
            "/vectors/search",
            None,
            [("vector", 0.0), ("vector", 0.0)],
        ),
        ("get", "/metrics", None, None),
        ("get", "/metrics/summary", None, None),
        ("get", "/dashboard/stats", None, None),
        ("get", "/dashboard/recent_events", None, None),
    ],
)
def test_endpoints_require_authentication(
    method: str, path: str, body: dict[str, Any] | None, params: list[Any] | None
) -> None:
    client = TestClient(app)
    request = getattr(client, method)
    if method == "get":
        res = request(path, params=params)
    elif body is not None:
        res = request(path, json=body)
    else:
        res = request(path)
    assert res.status_code == 401


def test_exception_logging_on_query(
    monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """Exception inside endpoint should be logged with traceback."""
    client = TestClient(app, raise_server_exceptions=False)

    def raise_error(*_: Any, **__: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(app.state.query_engine, "execute_cypher", raise_error)

    with caplog.at_level("ERROR"):
        res = client.get(
            "/query",
            params={"cypher": "MATCH (n)"},
            headers={"Authorization": f"Bearer {_token(client)}"},
        )

    assert res.status_code == 500
    assert any(rec.exc_info for rec in caplog.records)
    assert any(
        "Unhandled exception while processing request" in rec.getMessage()
        for rec in caplog.records
    )
