import os
import time
from pathlib import Path

import pytest
from testcontainers.compose import DockerCompose

from ume.event import Event, EventType
from ume.client import UMEClient
from ume.config import Settings
from ume.federation import ClusterReplicator


class DockerSettings(Settings):
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_RAW_EVENTS_TOPIC: str = "ume_federation_raw"
    KAFKA_CLEAN_EVENTS_TOPIC: str = "ume_federation_raw"
    KAFKA_GROUP_ID: str = "ume_federation_group"

    def __init__(self, broker: str) -> None:
        super().__init__()
        self.KAFKA_BOOTSTRAP_SERVERS = broker


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_federation_replication():
    compose_file = Path(__file__).parent / "compose" / "federation-compose.yml"
    with DockerCompose(str(compose_file)) as compose:
        rp1 = f"localhost:{compose.get_service_port('redpanda1', 9092)}"
        rp2 = f"localhost:{compose.get_service_port('redpanda2', 9092)}"

        settings1 = DockerSettings(rp1)
        client1 = UMEClient(settings1)

        now = int(time.time())
        client1.produce_event(
            Event(
                event_type=EventType.CREATE_NODE.value,
                timestamp=now,
                payload={"node_id": "a", "attributes": {"type": "Test"}},
            )
        )

        replicator = ClusterReplicator(settings1, rp2)
        replicator.replicate_once()
        replicator.stop()

        settings2 = DockerSettings(rp2)
        client2 = UMEClient(settings2)
        events = list(client2.consume_events(timeout=2))
        client1.close()
        client2.close()
        assert any(ev.payload.get("attributes", {}).get("type") == "Test" for ev in events)

