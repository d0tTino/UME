import json
from typing import cast

import pytest
from jsonschema import ValidationError

from ume.client import UMEClient, UMEClientError
from ume.config import Settings
from ume.event import EventType
from ume.event import Event


class DummyProducer:
    def __init__(self, conf):
        self.produced = []

    def produce(self, topic, value):
        self.produced.append((topic, value))

    def flush(self):
        pass


class DummyConsumer:
    def __init__(self, conf):
        self.messages = []

    def subscribe(self, topics):
        pass

    def poll(self, timeout):
        return self.messages.pop(0) if self.messages else None

    def close(self):
        pass


class DummySettings(Settings):
    KAFKA_RAW_EVENTS_TOPIC: str = "raw"
    KAFKA_CLEAN_EVENTS_TOPIC: str = "clean"
    KAFKA_BOOTSTRAP_SERVERS: str = "server"
    KAFKA_GROUP_ID: str = "gid"


def build_client(monkeypatch, consumer=None, producer=None):
    consumer = consumer or DummyConsumer
    producer = producer or DummyProducer
    monkeypatch.setattr("ume.client.Consumer", consumer)
    monkeypatch.setattr("ume.client.Producer", producer)
    return UMEClient(cast(Settings, DummySettings()))


def test_produce_event(monkeypatch):
    client = build_client(monkeypatch)
    event = Event(
        event_type=EventType.CREATE_NODE.value,
        timestamp=1,
        payload={},
        node_id="n1",
        target_node_id="",
        label="",
        source="s",
    )
    client.produce_event(event)
    produced = client.producer.produced[0]
    assert produced[0] == "raw"
    data = json.loads(produced[1].decode("utf-8"))
    assert data["event_type"] == "CREATE_NODE"


def test_produce_event_validation_error(monkeypatch):
    def bad_validate(_):
        raise ValidationError("bad")

    monkeypatch.setattr("ume.client.validate_event_dict", bad_validate)
    client = build_client(monkeypatch)
    event = Event(
        event_type=EventType.CREATE_NODE.value,
        timestamp=1,
        payload={},
        node_id="n1",
        target_node_id="",
        label="",
        source="s",
    )
    with pytest.raises(UMEClientError):
        client.produce_event(event)


def test_consume_events(monkeypatch):
    consumer = DummyConsumer({})
    msg_data = json.dumps(
        {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {}}
    ).encode()

    class DummyMsg:
        def __init__(self, value):
            self._value = value

        def error(self):
            return None

        def value(self):
            return self._value

    consumer.messages.append(DummyMsg(msg_data))
    client = build_client(monkeypatch, consumer=lambda conf: consumer)
    events = list(client.consume_events(timeout=0))
    assert len(events) == 1
    assert events[0].node_id == "n1"
    assert events[0].event_type == "CREATE_NODE"
