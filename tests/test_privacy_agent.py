import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest
from presidio_analyzer import RecognizerResult

root_dir = Path(__file__).resolve().parents[1]


@pytest.fixture()
def privacy_agent(monkeypatch):
    """Provide the privacy_agent module with a minimal ``ume`` package."""

    pkg = types.ModuleType("ume")
    pkg.__path__ = [str(root_dir / "src/ume")]
    monkeypatch.setitem(sys.modules, "ume", pkg)

    schemas_spec = importlib.util.spec_from_file_location(
        "ume.schemas",
        root_dir / "src/ume/schemas/__init__.py",
        submodule_search_locations=[str(root_dir / "src/ume/schemas")],
    )
    assert schemas_spec is not None and schemas_spec.loader is not None
    schemas_mod = importlib.util.module_from_spec(schemas_spec)
    monkeypatch.setitem(sys.modules, "ume.schemas", schemas_mod)
    schemas_spec.loader.exec_module(schemas_mod)

    pa_spec = importlib.util.spec_from_file_location(
        "ume.privacy_agent",
        root_dir / "src/ume/privacy_agent.py",
        submodule_search_locations=[str(root_dir / "src/ume")],
    )
    assert pa_spec is not None and pa_spec.loader is not None
    pa_mod = importlib.util.module_from_spec(pa_spec)
    monkeypatch.setitem(sys.modules, "ume.privacy_agent", pa_mod)
    pa_spec.loader.exec_module(pa_mod)

    yield pa_mod


class FakeAnalyzer:
    def __init__(self, results):
        self._results = results

    def analyze(self, text: str, language: str = "en"):
        return self._results


def test_redact_event_payload_with_pii(privacy_agent, monkeypatch):
    payload = {"email": "user@example.com"}
    results = [
        RecognizerResult(entity_type="EMAIL_ADDRESS", start=11, end=27, score=1.0)
    ]
    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer(results))
    redacted, flag = privacy_agent.redact_event_payload(payload)
    assert flag is True
    assert redacted == {"email": "<EMAIL_ADDRESS>"}


def test_redact_event_payload_without_pii(privacy_agent, monkeypatch):
    payload = {"message": "hello"}
    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer([]))
    redacted, flag = privacy_agent.redact_event_payload(payload)
    assert flag is False
    assert redacted == payload


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


def test_privacy_agent_end_to_end(privacy_agent, monkeypatch):
    payload = {"email": "user@example.com"}
    event = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n1",
        "payload": payload,
    }
    msg = FakeMessage(json.dumps(event).encode("utf-8"))

    consumer = FakeConsumer([msg])
    producer = FakeProducer()
    results = [
        RecognizerResult(entity_type="EMAIL_ADDRESS", start=11, end=27, score=1.0)
    ]

    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer(results))
    monkeypatch.setattr(privacy_agent, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(privacy_agent, "Producer", lambda conf: producer)
    monkeypatch.setattr(privacy_agent, "log_audit_entry", lambda *a, **k: None)
    monkeypatch.setattr(privacy_agent.settings, "KAFKA_PRODUCER_BATCH_SIZE", 10)
    monkeypatch.setattr(privacy_agent, "BATCH_SIZE", 10)

    privacy_agent.run_privacy_agent()

    clean_topic = privacy_agent.CLEAN_TOPIC
    quarantine_topic = privacy_agent.QUARANTINE_TOPIC

    clean_msg = next(val for (topic, val) in producer.produced if topic == clean_topic)
    quarantine_msg = next(
        val for (topic, val) in producer.produced if topic == quarantine_topic
    )

    assert json.loads(clean_msg.decode("utf-8"))["payload"] == {
        "email": "<EMAIL_ADDRESS>"
    }
    assert json.loads(quarantine_msg.decode("utf-8")) == {"original": payload}
    # Flush should only be called once at shutdown
    assert producer.flush_calls == 1


def test_privacy_agent_periodic_flush(privacy_agent, monkeypatch):
    payload = {"email": "user@example.com"}
    event = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n1",
        "payload": payload,
    }
    msgs = [FakeMessage(json.dumps(event).encode("utf-8")) for _ in range(3)]

    consumer = FakeConsumer(msgs)
    producer = FakeProducer()
    results = [
        RecognizerResult(entity_type="EMAIL_ADDRESS", start=11, end=27, score=1.0)
    ]

    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer(results))
    monkeypatch.setattr(privacy_agent, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(privacy_agent, "Producer", lambda conf: producer)
    monkeypatch.setattr(privacy_agent, "log_audit_entry", lambda *a, **k: None)
    monkeypatch.setattr(privacy_agent.settings, "KAFKA_PRODUCER_BATCH_SIZE", 3)
    monkeypatch.setattr(privacy_agent, "BATCH_SIZE", 3)

    privacy_agent.run_privacy_agent()

    # Flush should be called once when batch size reached and once at shutdown
    assert producer.flush_calls == 2
