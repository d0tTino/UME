import json
import pytest
from types import SimpleNamespace

from ume.pipeline import privacy_agent

pytest.importorskip("regopy")

class FakeAnalyzer:
    def analyze(self, text: str, language: str = "en"):
        return []

class FakeAnonymizer:
    def anonymize(self, text: str, analyzer_results):
        return SimpleNamespace(text=text)

class FakeMessage:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value

    def error(self):
        return None

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


def test_rego_policy_denies_event(monkeypatch):
    event = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "forbidden",
        "payload": {"node_id": "forbidden", "attributes": {}},
    }
    msg = FakeMessage(json.dumps(event).encode("utf-8"))

    consumer = FakeConsumer([msg])
    producer = FakeProducer()

    monkeypatch.setattr(privacy_agent, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(privacy_agent, "Producer", lambda conf: producer)
    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer())
    monkeypatch.setattr(privacy_agent, "_ANONYMIZER", FakeAnonymizer())
    monkeypatch.setattr(privacy_agent.settings, "KAFKA_PRODUCER_BATCH_SIZE", 1)
    monkeypatch.setattr(privacy_agent, "BATCH_SIZE", 1)

    privacy_agent.run_privacy_agent()

    quarantine = [
        val for topic, val in producer.produced if topic == privacy_agent.QUARANTINE_TOPIC
    ]
    assert len(quarantine) == 1
    assert not any(topic == privacy_agent.CLEAN_TOPIC for topic, _ in producer.produced)
    assert producer.flush_calls == 1
