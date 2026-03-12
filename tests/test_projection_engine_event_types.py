import json

from ume import MockGraph
from ume.services import projection_worker


class DummyMessage:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def value(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def error(self):
        return None


class DummyConsumer:
    def __init__(self, payloads: list[dict]) -> None:
        self._messages = [DummyMessage(payload) for payload in payloads]
        self._index = 0

    def poll(self, timeout: float = 1.0):
        if self._index >= len(self._messages):
            raise KeyboardInterrupt
        msg = self._messages[self._index]
        self._index += 1
        return msg

    def close(self) -> None:
        return None


def test_projection_engine_event_type_contract_import_path(monkeypatch) -> None:
    captured_event_types: list[str] = []

    def _capture_projector(_graph, *, classify=False):
        def _project(context):
            event = context.effective_event
            if event is not None:
                captured_event_types.append(event.event_type)
            return {}

        return _project

    monkeypatch.setattr(projection_worker, "build_graph_projector", _capture_projector)

    consumer = DummyConsumer(
        [
            {
                "eventType": "CREATE_NODE",
                "eventId": "evt-1",
                "timestamp": 1,
                "nodeId": "n1",
                "producerId": "p1",
                "tenant": "t1",
                "payload": {"node_id": "n1", "type": "User", "acl": {"t1": ["p1"]}},
            }
        ]
    )

    projection_worker.run_projection_worker(MockGraph(), consumer=consumer)

    assert captured_event_types == ["CREATE_NODE"]
