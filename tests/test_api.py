# ruff: noqa: E402
from fastapi.testclient import TestClient
import pytest
from typing import Any
import time
import threading
from pathlib import Path
from prometheus_client.parser import text_string_to_metric_families

faiss = pytest.importorskip("faiss")
if not hasattr(faiss, "IndexFlatL2"):
    pytest.skip("faiss is missing required functionality", allow_module_level=True)

from ume.api import app, configure_graph, configure_vector_store
from ume import api_deps as deps
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
        "/auth/token",
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


def test_metrics_summary(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("ume.embedding.generate_embedding", lambda _: [0.0, 0.0])
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
    assert "average_recall_score" in data


def test_metrics_after_recall(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("ume.embedding.generate_embedding", lambda _: [0.0, 1.0])
    configure_vector_store(VectorStore(dim=2, use_gpu=False))
    g = MockGraph()
    g.add_node("n1", {"embedding": [0.0, 1.0]})
    configure_graph(g)
    app.state.vector_store.add("n1", [0.0, 1.0])


    with TestClient(app) as client:
        token = _token(client)
        before = client.get("/metrics", headers={"Authorization": f"Bearer {token}"}).text

        def _metric_val(text: str, name: str, labels: dict[str, str] | None = None) -> float:
            for fam in text_string_to_metric_families(text):
                for sample in fam.samples:
                    if sample.name == name and (
                        not labels or all(sample.labels.get(k) == v for k, v in labels.items())
                    ):
                        return float(sample.value)
            return 0.0

        count_before = _metric_val(
            before,
            "ume_http_requests_total",
            {"method": "GET", "path": "/recall", "status": "200"},
        )
        latency_before = _metric_val(
            before, "ume_request_latency_seconds_count", {"method": "GET", "path": "/recall"}
        )
        recall_before = _metric_val(before, "ume_recall_score_count")
        recall_latency_before = _metric_val(before, "ume_recall_latency_ms_count")

        client.get(
            "/recall",
            params=[("vector", 0.0), ("vector", 1.0)],
            headers={"Authorization": f"Bearer {token}"},
        )

        after = client.get("/metrics", headers={"Authorization": f"Bearer {token}"}).text

        assert _metric_val(
            after,
            "ume_http_requests_total",
            {"method": "GET", "path": "/recall", "status": "200"},
        ) == count_before + 1
        assert _metric_val(
            after, "ume_request_latency_seconds_count", {"method": "GET", "path": "/recall"}
        ) == latency_before + 1
        assert _metric_val(after, "ume_recall_score_count") > recall_before
        assert _metric_val(after, "ume_recall_latency_ms_count") == recall_latency_before + 1


def test_metrics_summary_with_rate_limit(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("ume.embedding.generate_embedding", lambda _: [0.0, 0.0])
    configure_vector_store(VectorStore(dim=2, use_gpu=False))
    with TestClient(app) as client:
        token = _token(client)
        for _ in range(2):
            client.get(
                "/analytics/path/stream",
                params={"source": "a", "target": "b"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Forwarded-For": "127.0.0.1",
                },
            )
        res_limit = client.get(
            "/analytics/path/stream",
            params={"source": "a", "target": "b"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Forwarded-For": "127.0.0.1",
            },
        )
        assert res_limit.status_code == 429

        res = client.get(
            "/metrics/summary",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Forwarded-For": "127.0.0.1",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["request_count_by_status"].get("429", 0) >= 1


def test_dashboard_endpoints(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("ume.embedding.generate_embedding", lambda _: [0.0, 0.0])
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


@pytest.mark.parametrize(  # type: ignore[misc]
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
        ("get", "/vectors/benchmark", None, None),
        ("get", "/recall", None, [("query", "test")]),
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
    def raise_error(*_: Any, **__: Any) -> None:
        raise RuntimeError("boom")

    # Override the query engine dependency to ensure the error surfaces even if
    # previous tests replaced ``app.state.query_engine``.
    app.dependency_overrides[deps.get_query_engine] = lambda: type(
        "QE", (), {"execute_cypher": raise_error}
    )()

    client = TestClient(app, raise_server_exceptions=False)

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


def test_token_cleanup_task(monkeypatch: MonkeyPatch) -> None:
    from ume import api as api_mod

    monkeypatch.setattr(api_mod, "TOKEN_CLEANUP_INTERVAL", 0.01)
    monkeypatch.setattr(settings, "UME_OAUTH_TTL", 0.02)

    with TestClient(app) as client:
        token = _token(client)
        assert token in deps.TOKENS
        time.sleep(0.05)
        assert token not in deps.TOKENS


def test_api_ledger_compaction(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from ume.event_ledger import EventLedger

    ledger = EventLedger(str(tmp_path / "ledger.db"))
    for i in range(5):
        ledger.append(i, {"event_type": "E", "timestamp": i})
    ledger.update_bookmark(4)

    monkeypatch.setattr("ume.event_ledger.event_ledger", ledger)
    monkeypatch.setattr(settings, "UME_LEDGER_OFFSET_WINDOW", 2)
    monkeypatch.setattr(settings, "UME_LEDGER_COMPACTION_INTERVAL", 0.01)

    with TestClient(app) as client:
        _token(client)
        time.sleep(0.05)

    assert [o for o, _ in ledger.range()] == [2, 3, 4]


def test_issue_tokens_concurrently() -> None:
    """Concurrently issue OAuth tokens without triggering errors."""
    with TestClient(app) as client:
        tokens: list[str] = []
        errors: list[Exception] = []

        def worker() -> None:
            try:
                res = client.post(
                    "/auth/token",
                    data={
                        "username": settings.UME_OAUTH_USERNAME,
                        "password": settings.UME_OAUTH_PASSWORD,
                    },
                )
                tokens.append(res.json()["access_token"])
            except Exception as exc:  # pragma: no cover - unexpected
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(tokens) == 5
        for tok in tokens:
            deps.TOKENS.pop(tok, None)

