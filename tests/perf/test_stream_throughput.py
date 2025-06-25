import json
import os
import time

import pytest

pytest.importorskip("testcontainers")
from testcontainers.kafka import KafkaContainer

from ume.client import UMEClient
from ume.config import Settings
from ume.event import EventType


class DockerSettings(Settings):
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_RAW_EVENTS_TOPIC: str = "perf_raw"
    KAFKA_CLEAN_EVENTS_TOPIC: str = "perf_raw"
    KAFKA_GROUP_ID: str = "perf_group"
    UME_AUDIT_SIGNING_KEY: str = "test-key"

    def __init__(self, broker: str) -> None:
        super().__init__()
        self.KAFKA_BOOTSTRAP_SERVERS = broker


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_stream_throughput() -> None:
    events = 10_000
    with KafkaContainer() as kafka:
        broker = kafka.get_bootstrap_server()
        settings = DockerSettings(broker)
        client = UMEClient(settings)
        start = time.perf_counter()
        for i in range(events):
            msg = {
                "event_type": EventType.CREATE_NODE.value,
                "timestamp": i,
                "payload": {"node_id": f"n{i}", "attributes": {"type": "UserMemory"}},
                "node_id": f"n{i}",
            }
            client.producer.produce(settings.KAFKA_RAW_EVENTS_TOPIC, json.dumps(msg).encode())
        client.producer.flush()
        consumed = sum(1 for _ in client.consume_events(timeout=5))
        duration = time.perf_counter() - start
        client.close()
    assert consumed == events
    throughput = consumed / duration
    assert throughput > 10_000
    assert duration / consumed < 0.001
