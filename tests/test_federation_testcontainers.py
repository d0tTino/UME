import os
import time

import pytest
from testcontainers.core.container import DockerContainer

from ume.event import Event, EventType
from ume.client import UMEClient
from ume.config import Settings
from ume.federation import MirrorMakerDriver


class DockerSettings(Settings):
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_RAW_EVENTS_TOPIC: str = "ume_federation_raw"
    KAFKA_CLEAN_EVENTS_TOPIC: str = "ume_federation_raw"
    KAFKA_GROUP_ID: str = "ume_federation_group"
    UME_AUDIT_SIGNING_KEY: str = "test-key"

    def __init__(self, broker: str) -> None:
        super().__init__()
        self.KAFKA_BOOTSTRAP_SERVERS = broker


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_federation_replication_testcontainers():
    image = "docker.redpanda.com/redpandadata/redpanda:latest"
    cmd_base = (
        "redpanda start --smp 1 --overprovisioned --node-id {id} --check=false "
        "--kafka-addr PLAINTEXT://0.0.0.0:9092 "
        "--advertise-kafka-addr PLAINTEXT://127.0.0.1:9092"
    )
    rp1 = DockerContainer(image).with_exposed_ports(9092).with_command(cmd_base.format(id=0))
    rp2 = DockerContainer(image).with_exposed_ports(9092).with_command(cmd_base.format(id=1))
    try:
        rp1.start()
        rp2.start()
    except Exception as exc:
        pytest.skip(f"Redpanda not available: {exc}")
    broker1 = f"{rp1.get_container_host_ip()}:{rp1.get_exposed_port(9092)}"
    broker2 = f"{rp2.get_container_host_ip()}:{rp2.get_exposed_port(9092)}"

    settings1 = DockerSettings(broker1)
    mm = MirrorMakerDriver(broker1, broker2, [settings1.KAFKA_RAW_EVENTS_TOPIC])
    mm.start()

    client1 = UMEClient(settings1)
    now = int(time.time())
    client1.produce_event(
        Event(
            event_type=EventType.CREATE_NODE.value,
            timestamp=now,
            payload={"node_id": "a", "attributes": {"type": "Test"}},
        )
    )

    time.sleep(3)
    mm.stop()

    settings2 = DockerSettings(broker2)
    client2 = UMEClient(settings2)
    events = list(client2.consume_events(timeout=2))
    client1.close()
    client2.close()

    rp1.stop()
    rp2.stop()

    assert any(ev.payload.get("attributes", {}).get("type") == "Test" for ev in events)
