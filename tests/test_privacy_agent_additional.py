from types import SimpleNamespace
import json

from ume import privacy_agent

class FakeAnalyzer:
    def analyze(self, text: str, language: str = "en"):
        return [object()]  # non empty results

class FakeAnonymizer:
    def anonymize(self, text: str, analyzer_results):
        return SimpleNamespace(text="not-json")


def test_redact_event_payload_invalid_json(monkeypatch):
    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer())
    monkeypatch.setattr(privacy_agent, "_ANONYMIZER", FakeAnonymizer())
    payload = {"field": "value"}
    redacted, flag = privacy_agent.redact_event_payload(payload)
    assert redacted == payload
    assert flag is False

class Error:
    def __init__(self, code):
        self._code = code
    def code(self):
        return self._code

class ErrorMessage:
    def __init__(self, code):
        self._err = Error(code)
    def error(self):
        return self._err
    def value(self):
        return b""

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
    def produce(self, *args, **kwargs):
        self.produced.append(args)
    def flush(self):
        self.flush_calls += 1


def setup_agent(monkeypatch, consumer, producer):
    monkeypatch.setattr(privacy_agent, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(privacy_agent, "Producer", lambda conf: producer)
    monkeypatch.setattr(privacy_agent, "log_audit_entry", lambda *a, **k: None)
    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer())
    monkeypatch.setattr(privacy_agent, "_ANONYMIZER", FakeAnonymizer())
    monkeypatch.setattr(privacy_agent.settings, "KAFKA_PRODUCER_BATCH_SIZE", 1)
    monkeypatch.setattr(privacy_agent, "BATCH_SIZE", 1)


def test_kafka_error_is_skipped(monkeypatch):
    consumer = FakeConsumer([ErrorMessage(123)])
    producer = FakeProducer()
    setup_agent(monkeypatch, consumer, producer)
    privacy_agent.run_privacy_agent()
    assert producer.produced == []
    assert producer.flush_calls == 1


def test_invalid_json_skips_message(monkeypatch):
    msg = type("Msg", (), {"error": lambda self: None, "value": lambda self: b"{"})()
    consumer = FakeConsumer([msg])
    producer = FakeProducer()
    setup_agent(monkeypatch, consumer, producer)
    privacy_agent.run_privacy_agent()
    assert producer.produced == []


def test_validation_error_skips_message(monkeypatch):
    event = {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {}}
    msg = type("Msg", (), {"error": lambda self: None, "value": lambda self: json.dumps(event).encode("utf-8")})()
    consumer = FakeConsumer([msg])
    producer = FakeProducer()
    monkeypatch.setattr(privacy_agent, "validate_event_dict", lambda data: (_ for _ in ()).throw(privacy_agent.ValidationError("bad")))
    setup_agent(monkeypatch, consumer, producer)
    privacy_agent.run_privacy_agent()
    assert producer.produced == []
