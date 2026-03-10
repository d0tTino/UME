import json

from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume.config import settings
from ume.event_ledger import EventLedger
from ume.graph import MockGraph
import ume.graph_routes as graph_routes


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


def _read_graph_digest_payloads(client: TestClient, *, token: str, expected: int, headers: dict[str, str] | None = None):
    payloads: list[dict[str, object]] = []
    req_headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    if headers:
        req_headers.update(headers)
    with client.stream("GET", f"/graph/digest/stream?max_events={expected}", headers=req_headers) as response:
        assert response.status_code == 200
        pending_graph_digest = False
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("event: graph_digest"):
                pending_graph_digest = True
                continue
            if pending_graph_digest and line.startswith("data: "):
                payloads.append(json.loads(line[len("data: ") :]))
                pending_graph_digest = False
                if len(payloads) >= expected:
                    break
    return payloads


def test_graph_digest_stream_requires_auth_and_emits_digests(tmp_path, monkeypatch) -> None:
    configure_graph(MockGraph())
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    app.state.vector_store = type("VS", (), {"close": lambda self: None})()

    ledger = EventLedger(str(tmp_path / "realtime_auth.db"))
    _seed_ledger(ledger, 2)
    monkeypatch.setattr(graph_routes, "event_ledger", ledger)

    with TestClient(app) as client:
        unauth = client.get("/graph/digest/stream")
        assert unauth.status_code == 401

        payloads = _read_graph_digest_payloads(client, token=_token(client), expected=2)

    assert [item["offset"] for item in payloads] == [0, 1]
    assert payloads[0]["event_id"] == "evt-0"


def test_graph_digest_stream_reconnects_from_last_event_id(tmp_path, monkeypatch) -> None:
    configure_graph(MockGraph())
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    app.state.vector_store = type("VS", (), {"close": lambda self: None})()

    ledger = EventLedger(str(tmp_path / "realtime_reconnect.db"))
    _seed_ledger(ledger, 4)
    monkeypatch.setattr(graph_routes, "event_ledger", ledger)

    with TestClient(app) as client:
        token = _token(client)
        resumed = _read_graph_digest_payloads(
            client,
            token=token,
            expected=2,
            headers={"Last-Event-ID": "1"},
        )

    assert [item["offset"] for item in resumed] == [2, 3]
