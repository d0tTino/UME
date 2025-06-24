import os
import threading
import time

import pytest
from confluent_kafka import Consumer as KafkaConsumer

from ume.event import Event, EventType
from ume.client import UMEClient
from ume.config import Settings
from ume.neo4j_graph import Neo4jGraph
from ume.vector_store import VectorStore, VectorStoreListener
from ume._internal.listeners import register_listener, unregister_listener
from ume.processing import apply_event_to_graph
from ume.pipeline import privacy_agent


class DockerSettings(Settings):
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_RAW_EVENTS_TOPIC: str = "ume_e2e_raw"
    KAFKA_CLEAN_EVENTS_TOPIC: str = "ume_e2e_clean"
    KAFKA_QUARANTINE_TOPIC: str = "ume_e2e_quarantine"
    KAFKA_GROUP_ID: str = "ume_e2e_group"
    KAFKA_PRIVACY_AGENT_GROUP_ID: str = "ume_e2e_agent"
    UME_AUDIT_SIGNING_KEY: str = "test-key"

    def __init__(self, broker: str) -> None:
        super().__init__()
        self.KAFKA_BOOTSTRAP_SERVERS = broker


class FakeAnalyzer:
    def __init__(self, results):
        self._results = results

    def analyze(self, text: str, language: str = "en"):
        return self._results


class FakeAnonymizer:
    def anonymize(self, text: str, analyzer_results):
        return type("Result", (), {"text": text})()


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


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_privacy_agent_end_to_end(redpanda_service, neo4j_service, monkeypatch):
    broker = redpanda_service["bootstrap_servers"]
    settings = DockerSettings(broker)
    client = UMEClient(settings)

    store = VectorStore(dim=2, use_gpu=False)
    listener = VectorStoreListener(store)
    register_listener(listener)

    graph = Neo4jGraph(
        neo4j_service["uri"], neo4j_service["user"], neo4j_service["password"]
    )

    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer([]))
    monkeypatch.setattr(privacy_agent, "_ANONYMIZER", FakeAnonymizer())
    monkeypatch.setattr(privacy_agent, "Consumer", LimitingConsumer)
    monkeypatch.setattr(privacy_agent, "BOOTSTRAP_SERVERS", broker)
    monkeypatch.setattr(privacy_agent, "RAW_TOPIC", settings.KAFKA_RAW_EVENTS_TOPIC)
    monkeypatch.setattr(privacy_agent, "CLEAN_TOPIC", settings.KAFKA_CLEAN_EVENTS_TOPIC)
    monkeypatch.setattr(privacy_agent, "QUARANTINE_TOPIC", settings.KAFKA_QUARANTINE_TOPIC)
    monkeypatch.setattr(privacy_agent, "GROUP_ID", settings.KAFKA_PRIVACY_AGENT_GROUP_ID)
    monkeypatch.setattr(privacy_agent, "BATCH_SIZE", 1)

    agent_thread = threading.Thread(target=privacy_agent.run_privacy_agent)
    agent_thread.start()

    now = int(time.time())
    client.produce_event(
        Event(
            event_type=EventType.CREATE_NODE.value,
            timestamp=now,
            payload={"node_id": "n1", "attributes": {"embedding": [1.0, 0.0]}},
        )
    )

    agent_thread.join(timeout=10)

    events = list(client.consume_events(timeout=2))
    for ev in events:
        apply_event_to_graph(ev, graph)

    assert graph.get_node("n1") is not None
    assert store.query([1.0, 0.0], k=1) == ["n1"]

    graph.close()
    client.close()
    store.close()
    unregister_listener(listener)
