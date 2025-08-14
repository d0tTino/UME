import os
import threading
import json

import pytest
from fastapi.testclient import TestClient
from confluent_kafka import Consumer as KafkaConsumer

from ume.ingestion_api import app, producer_conf, settings as api_settings
from ume.pipeline import graph_consumer
from ume.event_ledger import EventLedger
from ume.graph import MockGraph
from ume.vector_store import VectorStoreListener
from ume._internal.listeners import register_listener, unregister_listener


class DummyVectorStore:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.vectors: dict[str, list[float]] = {}

    def add(self, vid: str, vector: list[float]) -> None:
        assert len(vector) == self.dim
        self.vectors[vid] = vector

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        def dist(v: list[float]) -> float:
            return sum((a - b) ** 2 for a, b in zip(v, vector))
        return [vid for vid, v in sorted(self.vectors.items(), key=lambda kv: dist(kv[1]))][:k]

    def close(self) -> None:
        pass


class LimitingConsumer(KafkaConsumer):
    def __init__(self, conf):
        super().__init__(conf)
        self.count = 0

    def poll(self, timeout: float = 1.0):
        if self.count >= 1:
            raise KeyboardInterrupt
        msg = super().poll(timeout)
        if msg is not None and not msg.error():
            self.count += 1
        return msg


class DummyMessage:
    def __init__(self, value: bytes, offset: int) -> None:
        self._value = value
        self._offset = offset

    def value(self) -> bytes:  # pragma: no cover - simple accessor
        return self._value

    def error(self):  # pragma: no cover - simple accessor
        return None

    def offset(self) -> int:  # pragma: no cover - simple accessor
        return self._offset


class DummyConsumer:
    def __init__(self, messages: list[DummyMessage]) -> None:
        self.messages = messages
        self.index = 0

    def subscribe(self, topics):  # pragma: no cover - simple stub
        self.topics = topics

    def poll(self, timeout: float = 1.0):
        if self.index >= len(self.messages):
            raise KeyboardInterrupt
        msg = self.messages[self.index]
        self.index += 1
        return msg

    def close(self) -> None:  # pragma: no cover - simple stub
        pass


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled"
)
def test_pipeline_end_to_end(tmp_path, monkeypatch):
    try:
        from testcontainers.core.container import DockerContainer
    except Exception as exc:
        pytest.skip(f"Docker containers not available: {exc}")

    try:
        container = DockerContainer(
            "docker.redpanda.com/redpandadata/redpanda:latest"
        )
        container.with_exposed_ports(9092)
        container.with_command(
            "redpanda start --smp 1 --overprovisioned --node-id 0 --check=false "
            "--kafka-addr PLAINTEXT://0.0.0.0:9092 "
            "--advertise-kafka-addr PLAINTEXT://127.0.0.1:9092"
        )
        container.start()
    except Exception as exc:  # pragma: no cover - environment issues
        pytest.skip(f"Redpanda not available: {exc}")

    broker = f"{container.get_container_host_ip()}:{container.get_exposed_port(9092)}"

    object.__setattr__(api_settings, "KAFKA_BOOTSTRAP_SERVERS", broker)
    object.__setattr__(api_settings, "KAFKA_RAW_EVENTS_TOPIC", "pipeline_raw")
    object.__setattr__(api_settings, "UME_AUDIT_SIGNING_KEY", "test-key")
    producer_conf["bootstrap.servers"] = broker

    object.__setattr__(graph_consumer, "BOOTSTRAP_SERVERS", broker)
    object.__setattr__(graph_consumer, "NODE_TOPIC", "pipeline_nodes")
    object.__setattr__(graph_consumer, "EDGE_TOPIC", "pipeline_edges")
    object.__setattr__(graph_consumer, "DEFAULT_GROUP_ID", "pipeline_group")

    ledger = EventLedger(str(tmp_path / "ledger.db"))
    monkeypatch.setattr(graph_consumer, "event_ledger", ledger)
    monkeypatch.setattr(graph_consumer, "Consumer", LimitingConsumer)
    monkeypatch.setattr(graph_consumer, "ssl_config", lambda: {})

    graph = MockGraph()
    store = DummyVectorStore(dim=2)
    listener = VectorStoreListener(store)
    register_listener(listener)

    consumer_thread = threading.Thread(
        target=graph_consumer.run_graph_consumer,
        args=(graph,),
        kwargs={"group_id": "pipeline_group"},
    )
    consumer_thread.start()

    event = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n1",
        "payload": {"node_id": "n1", "attributes": {"embedding": [1.0, 0.0]}},
    }

    with TestClient(app) as client:
        res = client.post("/events", json=event)
        assert res.status_code == 202

    consumer_thread.join(timeout=10)
    assert not consumer_thread.is_alive(), "graph consumer did not terminate"

    assert graph.get_node("n1") == {"embedding": [1.0, 0.0]}
    assert store.query([1.0, 0.0], k=1) == ["n1"]

    ledger.close()
    unregister_listener(listener)
    container.stop()


def test_generic_events_go_to_ledger(tmp_path, monkeypatch, caplog):
    msg_data = {
        "eventType": "CUSTOM",
        "timestamp": "1970-01-01T00:00:01Z",
        "payload": {"foo": "bar"},
    }
    msg = DummyMessage(json.dumps(msg_data).encode("utf-8"), 0)
    consumer = DummyConsumer([msg])
    ledger = EventLedger(str(tmp_path / "ledger.db"))

    monkeypatch.setattr(graph_consumer, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(graph_consumer, "ssl_config", lambda: {})
    monkeypatch.setattr(graph_consumer, "event_ledger", ledger)

    graph = MockGraph()
    with caplog.at_level("WARNING"):
        graph_consumer.run_graph_consumer(graph, group_id="g")

    assert ledger.range() == [
        (0, {"eventType": "CUSTOM", "timestamp": 1, "payload": {"foo": "bar"}})
    ]
    assert ledger.last_processed_offset == 0
    assert not graph.get_all_node_ids()
    assert any("Unknown event type" in rec.message for rec in caplog.records)


def test_generic_enveloped_events_go_to_ledger(tmp_path, monkeypatch, caplog):
    envelope = {
        "schema_version": "3.0.0",
        "event": {
            "eventType": "CUSTOM",
            "timestamp": "1970-01-01T00:00:01Z",
            "payload": {"foo": "bar"},
        },
    }
    msg = DummyMessage(json.dumps(envelope).encode("utf-8"), 0)
    consumer = DummyConsumer([msg])
    ledger = EventLedger(str(tmp_path / "ledger.db"))

    monkeypatch.setattr(graph_consumer, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(graph_consumer, "ssl_config", lambda: {})
    monkeypatch.setattr(graph_consumer, "event_ledger", ledger)

    graph = MockGraph()
    with caplog.at_level("WARNING"):
        graph_consumer.run_graph_consumer(graph, group_id="g")

    assert ledger.range() == [
        (0, {"eventType": "CUSTOM", "timestamp": 1, "payload": {"foo": "bar"}})
    ]
    assert ledger.last_processed_offset == 0
    assert not graph.get_all_node_ids()
    assert any("Unknown event type" in rec.message for rec in caplog.records)
