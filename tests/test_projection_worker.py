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


def test_projection_worker_consumes_clean_events_and_mutates_graph() -> None:
    consumer = DummyConsumer(
        [
            {
                "eventType": "CREATE_NODE",
                "eventId": "evt-1",
                "timestamp": 1,
                "nodeId": "n1",
                "payload": {"node_id": "n1", "attributes": {"type": "User"}},
            }
        ]
    )

    graph = MockGraph()
    projection_worker.run_projection_worker(graph, consumer=consumer)

    assert graph.get_node("n1") == {"type": "User"}
