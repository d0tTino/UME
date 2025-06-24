# mypy: ignore-errors
import json
from types import SimpleNamespace
import importlib.util
from pathlib import Path
import sys

module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "consumer_demo.py"
spec = importlib.util.spec_from_file_location("ume.consumer_demo", module_path)
assert spec and spec.loader
consumer_demo = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = consumer_demo
spec.loader.exec_module(consumer_demo)


class DummyMessage:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value

    def error(self):
        return None


class DummyConsumer:
    def __init__(self, messages):
        self.messages = messages
        self.closed = False

    def subscribe(self, topics):
        self.topics = topics

    def poll(self, timeout=1.0):
        if self.messages:
            return self.messages.pop(0)
        raise KeyboardInterrupt

    def close(self):
        self.closed = True


def test_consumer_demo_processes_messages(monkeypatch):
    data = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "payload": {"text": "hi"},
        "node_id": "n1",
    }
    msg = DummyMessage(json.dumps(data).encode("utf-8"))
    consumer = DummyConsumer([msg])
    monkeypatch.setattr(consumer_demo, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(
        consumer_demo, "KafkaError", SimpleNamespace(_PARTITION_EOF=None)
    )
    parsed = []
    monkeypatch.setattr(consumer_demo, "parse_event", lambda d: parsed.append(d) or d)
    monkeypatch.setattr(consumer_demo, "generate_embedding", lambda text: [0.0])

    consumer_demo.main()

    assert consumer.closed
    assert parsed
    assert parsed[0]["payload"]["embedding"] == [0.0]

