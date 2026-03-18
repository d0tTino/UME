import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ume.config import settings
from ume.event_ledger import EventLedger
from ume.graph import MockGraph
import ume.dashboard_routes as dashboard_routes


class _VectorStoreStub:
    def __init__(self) -> None:
        self.idx_to_id = ["n0", "n1"]

    def close(self) -> None:
        return None


def _build_client(graph: MockGraph, vector_store: _VectorStoreStub) -> TestClient:
    app = FastAPI()
    app.include_router(dashboard_routes.router)
    app.dependency_overrides[dashboard_routes.get_current_role] = lambda: settings.UME_OAUTH_ROLE
    dashboard_routes.get_graph = lambda: graph
    dashboard_routes.get_vector_store = lambda: vector_store
    return TestClient(app)


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


def _read_dashboard_frames(
    client: TestClient,
    *,
    expected: int,
    headers: dict[str, str] | None = None,
    query: str = "",
) -> tuple[list[dict[str, object]], str | None]:
    frames: list[dict[str, object]] = []
    req_headers = {"Authorization": "Bearer test-token", "Accept": "text/event-stream"}
    if headers:
        req_headers.update(headers)

    content_type = None
    with client.stream("GET", f"/dashboard/stream?max_events={expected}{query}", headers=req_headers) as response:
        assert response.status_code == 200
        content_type = response.headers.get("content-type")
        current: dict[str, str] = {}
        for line in response.iter_lines():
            if line == "":
                if current.get("data"):
                    frames.append(
                        {
                            "event": current.get("event", "message"),
                            "id": current.get("id"),
                            "data": json.loads(current["data"]),
                        }
                    )
                current = {}
                if len(frames) >= expected:
                    break
                continue
            if line.startswith("event:"):
                current["event"] = line.split(":", 1)[1].strip()
            elif line.startswith("id:"):
                current["id"] = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                current["data"] = current.get("data", "") + line.split(":", 1)[1].strip()
    return frames, content_type


def test_dashboard_stream_emits_sanitized_updates(tmp_path, monkeypatch) -> None:
    graph = MockGraph()
    graph.add_node("n0", {})
    graph.add_node("n1", {})
    graph.add_edge("n0", "n1", "L")
    vector_store = _VectorStoreStub()

    ledger = EventLedger(str(tmp_path / "dashboard_stream.db"))
    _seed_ledger(ledger, 2)
    monkeypatch.setattr(dashboard_routes, "event_ledger", ledger)

    with _build_client(graph, vector_store) as client:
        frames, content_type = _read_dashboard_frames(client, expected=2)

    assert content_type is not None and content_type.startswith("text/event-stream")
    assert [frame["event"] for frame in frames] == ["dashboard_digest", "dashboard_digest"]
    assert [frame["id"] for frame in frames] == ["0", "1"]
    assert [frame["data"]["cursor_offset"] for frame in frames] == [0, 1]
    latest = frames[-1]["data"]
    assert latest["stats"] == {"node_count": 2, "edge_count": 1, "vector_index_size": 2}
    assert isinstance(latest["recent_events"], list)
    assert "payload_hash" in latest["recent_events"][0]
    assert "payload" not in latest["recent_events"][0]


def test_dashboard_stream_resumes_with_last_event_id_header_precedence(tmp_path, monkeypatch) -> None:
    ledger = EventLedger(str(tmp_path / "dashboard_stream_resume.db"))
    _seed_ledger(ledger, 5)
    monkeypatch.setattr(dashboard_routes, "event_ledger", ledger)

    with _build_client(MockGraph(), _VectorStoreStub()) as client:
        frames, _ = _read_dashboard_frames(
            client,
            expected=2,
            headers={"Last-Event-ID": "1"},
            query="&lastEventId=0",
        )

    assert [frame["id"] for frame in frames] == ["2", "3"]
    assert [frame["data"]["cursor_offset"] for frame in frames] == [2, 3]


def test_dashboard_stream_uses_greater_of_cursor_and_replay_marker(tmp_path, monkeypatch) -> None:
    ledger = EventLedger(str(tmp_path / "dashboard_stream_cursor.db"))
    _seed_ledger(ledger, 5)
    monkeypatch.setattr(dashboard_routes, "event_ledger", ledger)

    with _build_client(MockGraph(), _VectorStoreStub()) as client:
        frames, _ = _read_dashboard_frames(
            client,
            expected=1,
            query="&cursor=4&lastEventId=1",
        )

    assert [frame["id"] for frame in frames] == ["4"]
    assert frames[0]["data"]["cursor_offset"] == 4
