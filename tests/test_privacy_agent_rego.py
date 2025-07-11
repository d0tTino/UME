import json
import pytest
from types import SimpleNamespace

from ume.pipeline import privacy_agent

pytest.importorskip("regopy")

class FakeAnalyzer:
    def analyze(self, text: str, language: str = "en") -> list[object]:
        return []

class FakeAnonymizer:
    def anonymize(self, text: str, analyzer_results: object) -> SimpleNamespace:
        return SimpleNamespace(text=text)

class FakeMessage:
    def __init__(self, value: bytes, offset: int = 0) -> None:
        self._value = value
        self._offset = offset

    def value(self) -> bytes:
        return self._value

    def error(self) -> None:
        return None

    def offset(self) -> int:
        return self._offset

class FakeConsumer:
    def __init__(self, messages: list[FakeMessage]) -> None:
        self._messages = messages

    def poll(self, timeout: float = 1.0) -> FakeMessage:
        if self._messages:
            return self._messages.pop(0)
        raise KeyboardInterrupt

    def subscribe(self, topics: list[str]) -> None:
        pass

    def close(self) -> None:
        pass

class FakeProducer:
    def __init__(self) -> None:
        self.produced: list[tuple[str, bytes]] = []
        self.flush_calls = 0

    def produce(self, topic: str, value: bytes, *args: object, **kwargs: object) -> None:
        self.produced.append((topic, value))

    def flush(self) -> None:
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
    monkeypatch.setattr(privacy_agent.settings, "KAFKA_PRODUCER_BATCH_SIZE", 1)  # type: ignore[attr-defined]
    monkeypatch.setattr(privacy_agent, "BATCH_SIZE", 1)

    privacy_agent.run_privacy_agent()

    quarantine = [
        val for topic, val in producer.produced if topic == privacy_agent.QUARANTINE_TOPIC
    ]
    assert len(quarantine) == 1
    assert not any(topic == privacy_agent.CLEAN_TOPIC for topic, _ in producer.produced)
    assert producer.flush_calls == 1


class FakeLedger:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed

    def has_consent(self, user_id: str, scope: str) -> bool:  # noqa: D401
        return self.allowed


def _setup_agent(monkeypatch: pytest.MonkeyPatch, consumer: FakeConsumer, producer: FakeProducer, ledger: FakeLedger) -> None:
    monkeypatch.setattr(privacy_agent, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(privacy_agent, "Producer", lambda conf: producer)
    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer())
    monkeypatch.setattr(privacy_agent, "_ANONYMIZER", FakeAnonymizer())
    monkeypatch.setattr(privacy_agent, "consent_ledger", ledger)
    monkeypatch.setattr(privacy_agent.settings, "KAFKA_PRODUCER_BATCH_SIZE", 1)  # type: ignore[attr-defined]
    monkeypatch.setattr(privacy_agent, "BATCH_SIZE", 1)


def test_event_without_consent_goes_to_quarantine(monkeypatch: pytest.MonkeyPatch) -> None:
    event = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n1",
        "payload": {"node_id": "n1", "user_id": "u1", "scope": "profile", "attributes": {}},
    }
    msg = FakeMessage(json.dumps(event).encode("utf-8"))

    consumer = FakeConsumer([msg])
    producer = FakeProducer()
    ledger = FakeLedger(False)

    _setup_agent(monkeypatch, consumer, producer, ledger)

    privacy_agent.run_privacy_agent()

    assert not any(topic == privacy_agent.CLEAN_TOPIC for topic, _ in producer.produced)
    assert any(topic == privacy_agent.QUARANTINE_TOPIC for topic, _ in producer.produced)


def test_event_with_consent_published(monkeypatch: pytest.MonkeyPatch) -> None:
    event = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n2",
        "payload": {"node_id": "n2", "user_id": "u1", "scope": "profile", "attributes": {}},
    }
    msg = FakeMessage(json.dumps(event).encode("utf-8"))

    consumer = FakeConsumer([msg])
    producer = FakeProducer()
    ledger = FakeLedger(True)

    _setup_agent(monkeypatch, consumer, producer, ledger)

    privacy_agent.run_privacy_agent()

    assert any(topic == privacy_agent.CLEAN_TOPIC for topic, _ in producer.produced)
