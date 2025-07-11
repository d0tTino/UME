import json

from ume.pipeline import privacy_agent
from ume.event_ledger import EventLedger
from ume.replay import replay_from_ledger
from ume.persistent_graph import PersistentGraph


class FakeAnalyzer:
    def analyze(self, text: str, language: str = "en"):
        return []


class FakeAnonymizer:
    def anonymize(self, text: str, analyzer_results):
        return type("Result", (), {"text": text})()


class FakeMessage:
    def __init__(self, value: bytes, offset: int = 0):
        self._value = value
        self._offset = offset

    def value(self) -> bytes:
        return self._value

    def error(self):
        return None

    def offset(self) -> int:
        return self._offset


class FakeConsumer:
    def __init__(self, messages):
        self._messages = messages

    def poll(self, timeout=1.0):
        if self._messages:
            return self._messages.pop(0)
        raise KeyboardInterrupt

    def subscribe(self, topics):
        pass

    def close(self):
        pass


class FakeProducer:
    def __init__(self):
        self.produced = []
        self.flush_calls = 0

    def produce(self, topic, value, *args, **kwargs):
        self.produced.append((topic, value))

    def flush(self):
        self.flush_calls += 1


def test_privacy_agent_writes_to_ledger_and_replay(tmp_path, monkeypatch):
    event = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n1",
        "payload": {"node_id": "n1"},
    }
    msg = FakeMessage(json.dumps(event).encode("utf-8"), offset=5)

    consumer = FakeConsumer([msg])
    producer = FakeProducer()
    ledger = EventLedger(str(tmp_path / "ledger.db"))

    monkeypatch.setattr(privacy_agent, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(privacy_agent, "Producer", lambda conf: producer)
    monkeypatch.setattr(privacy_agent, "event_ledger", ledger)
    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer())
    monkeypatch.setattr(privacy_agent, "_ANONYMIZER", FakeAnonymizer())
    monkeypatch.setattr(privacy_agent.settings, "KAFKA_PRODUCER_BATCH_SIZE", 1)
    monkeypatch.setattr(privacy_agent, "BATCH_SIZE", 1)

    privacy_agent.run_privacy_agent()

    entries = ledger.range()
    assert len(entries) == 1
    assert entries[0][0] == 5
    assert entries[0][1]["node_id"] == "n1"

    graph = PersistentGraph(":memory:")
    last = replay_from_ledger(graph, ledger)
    assert graph.get_node("n1") is not None
    assert last == 5
    graph.close()
    ledger.close()
