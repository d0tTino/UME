import json
import os

import pytest

pytest.importorskip("testcontainers")
from testcontainers.kafka import KafkaContainer
from confluent_kafka import Producer, Consumer

from ume.graph import MockGraph
from ume import projection_engine


class LimitingConsumer(Consumer):
    """Kafka consumer that stops after consuming one message."""

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
def test_projection_engine_kafka() -> None:
    """Projection engine consumes sanitized events and updates the graph."""
    with KafkaContainer() as kafka:
        broker = kafka.get_bootstrap_server()
        topic = "ume-clean-events"
        projection_engine.BOOTSTRAP_SERVERS = broker
        projection_engine.TOPIC = topic
        projection_engine.GROUP_ID = "test-group"

        producer = Producer({"bootstrap.servers": broker})
        event = {
            "eventType": "CREATE_NODE",
            "timestamp": 1,
            "nodeId": "n1",
            "payload": {"type": "User"},
        }
        producer.produce(topic, json.dumps(event).encode("utf-8"))
        producer.flush()

        consumer_conf = {
            "bootstrap.servers": broker,
            "group.id": "test-group",
            "auto.offset.reset": "earliest",
        }
        consumer = LimitingConsumer(consumer_conf)
        consumer.subscribe([topic])

        graph = MockGraph()
        projection_engine.run_projection_engine(graph, consumer=consumer)
        consumer.close()

        assert graph.get_node("n1") == {"type": "User"}
