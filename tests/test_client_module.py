import json
import importlib.util
from typing import Any, Callable, cast

import pytest
from jsonschema import ValidationError

from ume.client import UMEClient, UMEClientError
from ume.config import Settings
from ume.event import EventType
from ume.event import Event


class DummyProducer:
    def __init__(self, conf: Any) -> None:
        self.produced: list[tuple[str, bytes]] = []

    def produce(self, topic: str, value: bytes) -> None:
        self.produced.append((topic, value))

    def flush(self) -> None:
        pass


class DummyConsumer:
    def __init__(self, conf: Any) -> None:
        self.messages: list[Any] = []

    def subscribe(self, topics: list[str]) -> None:
        pass

    def poll(self, timeout: float) -> Any | None:
        return self.messages.pop(0) if self.messages else None

    def close(self) -> None:
        pass


class DummySettings(Settings):
    KAFKA_RAW_EVENTS_TOPIC: str = "raw"
    KAFKA_CLEAN_EVENTS_TOPIC: str = "clean"
    KAFKA_BOOTSTRAP_SERVERS: str = "server"
    KAFKA_GROUP_ID: str = "gid"


def build_client(
    monkeypatch: pytest.MonkeyPatch,
    consumer: Callable[[Any], DummyConsumer] | type[DummyConsumer] | None = None,
    producer: Callable[[Any], DummyProducer] | type[DummyProducer] | None = None,
) -> UMEClient:
    consumer = consumer or DummyConsumer
    producer = producer or DummyProducer
    monkeypatch.setattr("ume.client.Consumer", consumer)
    monkeypatch.setattr("ume.client.Producer", producer)
    return UMEClient(cast(Settings, DummySettings()))


def test_produce_event(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_produce_event_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def bad_validate(_: Any) -> None:
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


def test_consume_events(monkeypatch: pytest.MonkeyPatch) -> None:
    consumer = DummyConsumer({})
    msg_data = json.dumps(
        {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {}}
    ).encode()

    class DummyMsg:
        def __init__(self, value: bytes) -> None:
            self._value = value

        def error(self) -> None:
            return None

        def value(self) -> bytes:
            return self._value

    consumer.messages.append(DummyMsg(msg_data))
    client = build_client(monkeypatch, consumer=lambda conf: consumer)
    events = list(client.consume_events(timeout=0))
    assert len(events) == 1
    assert events[0].node_id == "n1"
    assert events[0].event_type == "CREATE_NODE"


@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is None,
    reason="sentence-transformers not installed",
)
def test_consume_events_without_embedding(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "ume.embedding":
            raise ImportError("optional dependency missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    import sys
    sys.modules.pop("ume.embedding", None)

    consumer = DummyConsumer({})
    msg_data = json.dumps(
        {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {"t": "x"}}
    ).encode()

    class DummyMsg:
        def __init__(self, value: bytes) -> None:
            self._value = value

        def error(self) -> None:
            return None

        def value(self) -> bytes:
            return self._value

    consumer.messages.append(DummyMsg(msg_data))
    client = build_client(monkeypatch, consumer=lambda conf: consumer)
    with caplog.at_level("WARNING"):
        events = list(client.consume_events(timeout=0))

    assert len(events) == 1
    assert "embedding" not in events[0].payload
    assert any(
        "skipping embedding generation" in rec.message.lower() for rec in caplog.records
    )


def test_consume_events_invalid_message(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    consumer = DummyConsumer({})

    class DummyMsg:
        def __init__(self, value: bytes) -> None:
            self._value = value

        def error(self) -> None:
            return None

        def value(self) -> bytes:
            return self._value

    invalid = b"{bad json"
    valid = json.dumps(
        {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {}}
    ).encode()

    consumer.messages.append(DummyMsg(invalid))
    consumer.messages.append(DummyMsg(valid))

    client = build_client(monkeypatch, consumer=lambda conf: consumer)
    with caplog.at_level("WARNING"):
        events = list(client.consume_events(timeout=0))

    assert len(events) == 1
    assert events[0].node_id == "n1"
    assert any("invalid" in rec.message.lower() for rec in caplog.records)

