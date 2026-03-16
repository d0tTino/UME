import json

from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume.config import settings
from ume.event_ledger import EventLedger
from ume.graph import MockGraph
import ume.dashboard_routes as dashboard_routes


class _VectorStoreStub:
    def __init__(self) -> None:
        self.idx_to_id = ["n0", "n1"]

    def close(self) -> None:
        return None


def _token(client: TestClient) -> str:
    response = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return response.json()["access_token"]


def _seed_ledger(ledger: EventLedger, count: int) -> None:
    for offset in range(count):
        ledger.append(
            offset,
            {
                "eventType": "CREATE_NODE",
                "eventId": f"evt-{offset}",
                "timestamp": offset + 1,
                "sourceService": "test",
                "node_id": f"n{offset}",
                "payload": {"node_id": f"n{offset}", "attributes": {"name": f"N{offset}"}},
            },
        )


def _read_dashboard_digest_payloads(
    client: TestClient,
    *,
    token: str,
    expected: int,
    headers: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    req_headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    if headers:
        req_headers.update(headers)

    with client.stream("GET", f"/dashboard/stream?max_events={expected}", headers=req_headers) as response:
        assert response.status_code == 200
        pending = False
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("event: dashboard_digest"):
                pending = True
                continue
            if pending and line.startswith("data: "):
                payloads.append(json.loads(line[len("data: ") :]))
                pending = False
                if len(payloads) >= expected:
                    break
    return payloads


def test_dashboard_stream_emits_sanitized_updates(tmp_path, monkeypatch) -> None:
    graph = MockGraph()
    graph.add_node("n0", {})
    graph.add_node("n1", {})
    graph.add_edge("n0", "n1", "L")
    configure_graph(graph)
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    app.state.vector_store = _VectorStoreStub()

    ledger = EventLedger(str(tmp_path / "dashboard_stream.db"))
    _seed_ledger(ledger, 2)
    monkeypatch.setattr(dashboard_routes, "event_ledger", ledger)

    with TestClient(app) as client:
        payloads = _read_dashboard_digest_payloads(client, token=_token(client), expected=2)

    assert [item["cursor_offset"] for item in payloads] == [0, 1]
    latest = payloads[-1]
    assert latest["stats"] == {"node_count": 2, "edge_count": 1, "vector_index_size": 2}
    assert isinstance(latest["recent_events"], list)
    assert "payload_hash" in latest["recent_events"][0]


def test_dashboard_stream_resumes_with_last_event_id(tmp_path, monkeypatch) -> None:
    configure_graph(MockGraph())
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    app.state.vector_store = _VectorStoreStub()

    ledger = EventLedger(str(tmp_path / "dashboard_stream_resume.db"))
    _seed_ledger(ledger, 4)
    monkeypatch.setattr(dashboard_routes, "event_ledger", ledger)

    with TestClient(app) as client:
        resumed = _read_dashboard_digest_payloads(
            client,
            token=_token(client),
            expected=2,
            headers={"Last-Event-ID": "1"},
        )

    assert [item["cursor_offset"] for item in resumed] == [2, 3]
