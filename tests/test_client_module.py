import json
from types import ModuleType
import sys
import pytest

from ume import client
from ume.event import Event

class DummyProducer:
    def __init__(self):
        self.produced = []
        self.flushed = False
        self.flush_count = 0

    def produce(self, topic, value):
        self.produced.append((topic, value))

    def flush(self):
        self.flushed = True
        self.flush_count += 1

class DummyConsumer:
    def __init__(self, messages):
        self.messages = messages
        self.closed = False

    def subscribe(self, topics):
        pass

    def poll(self, timeout=1.0):
        return self.messages.pop(0) if self.messages else None

    def close(self):
        self.closed = True

class DummyMessage:
    def __init__(self, value, error=None):
        self._value = value
        self._error = error

    def value(self):
        return self._value

    def error(self):
        return self._error

class DummyKafkaError:
    def code(self):
        return None

class DummySettings:
    KAFKA_RAW_EVENTS_TOPIC = "raw"
    KAFKA_CLEAN_EVENTS_TOPIC = "clean"
    KAFKA_BOOTSTRAP_SERVERS = "server"
    KAFKA_GROUP_ID = "group"
    KAFKA_PRODUCER_BATCH_SIZE = 10

@pytest.fixture(autouse=True)
def embed_module(monkeypatch):
    module = ModuleType("ume.embedding")
    module.generate_embedding = lambda text: [0.0]  # type: ignore[attr-defined]
    sys.modules['ume.embedding'] = module
    yield
    sys.modules.pop('ume.embedding')

def make_client(monkeypatch, msgs=None, batch_size=10):
    producer = DummyProducer()
    consumer = DummyConsumer(msgs or [])
    monkeypatch.setattr(client, 'Producer', lambda conf: producer)
    monkeypatch.setattr(client, 'Consumer', lambda conf: consumer)
    settings = DummySettings()
    settings.KAFKA_PRODUCER_BATCH_SIZE = batch_size
    return client.UMEClient(settings), producer, consumer  # type: ignore[arg-type]

def test_produce_event(monkeypatch):
    c, prod, _ = make_client(monkeypatch)
    event = Event(
        event_type="CREATE_NODE",
        timestamp=1,
        payload={},
        node_id="n",
        source="test",
        target_node_id="unused",
        label="",
    )
    c.produce_event(event)
    assert prod.flush_count == 0
    topic, value = prod.produced[0]
    assert topic == "raw"
    data = json.loads(value.decode("utf-8"))
    assert data["schema_version"] == client.DEFAULT_VERSION
    assert data["event"]["node_id"] == "n"


def test_flush_after_batch(monkeypatch):
    c, prod, _ = make_client(monkeypatch, batch_size=2)
    event = Event(
        event_type="CREATE_NODE",
        timestamp=1,
        payload={},
        node_id="n",
        source="test",
        target_node_id="unused",
        label="",
    )
    c.produce_event(event)
    assert prod.flush_count == 0
    c.produce_event(event)
    assert prod.flush_count == 1


def test_flush_on_close(monkeypatch):
    c, prod, _ = make_client(monkeypatch, batch_size=5)
    event = Event(
        event_type="CREATE_NODE",
        timestamp=1,
        payload={},
        node_id="n",
        source="test",
        target_node_id="unused",
        label="",
    )
    c.produce_event(event)
    assert prod.flush_count == 0
    c.close()
    assert prod.flush_count == 1


def test_no_flush_without_pending(monkeypatch):
    c, prod, _ = make_client(monkeypatch)
    c.close()
    assert prod.flush_count == 0

def test_produce_event_invalid(monkeypatch):
    c, prod, _ = make_client(monkeypatch)
    bad_event = Event(
        event_type="CREATE_NODE",
        timestamp=1,
        payload={},
        target_node_id="unused",
        label="",
    )
    with pytest.raises(client.UMEClientError):
        c.produce_event(bad_event)
    assert not prod.produced

def test_consume_events(monkeypatch):
    data = {
        "schema_version": client.DEFAULT_VERSION,
        "event": {
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "payload": {"text": "hi"},
            "node_id": "n",
        },
    }
    msg = DummyMessage(json.dumps(data).encode("utf-8"))
    c, _, consumer = make_client(monkeypatch, [msg])
    events = list(c.consume_events())
    assert events[0].payload["embedding"] == [0.0]
    assert consumer.closed is False
    c.close()
    assert consumer.closed
