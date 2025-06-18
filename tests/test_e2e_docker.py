import os
import time

import pytest

from ume.event import Event, EventType
from ume.client import UMEClient
from ume.config import Settings
from ume.neo4j_graph import Neo4jGraph
from ume.processing import apply_event_to_graph


class DockerSettings(Settings):
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_RAW_EVENTS_TOPIC: str = "ume_e2e_raw"
    KAFKA_CLEAN_EVENTS_TOPIC: str = "ume_e2e_raw"
    KAFKA_GROUP_ID: str = "ume_e2e_group"

    def __init__(self, broker: str) -> None:
        super().__init__()
        self.KAFKA_BOOTSTRAP_SERVERS = broker


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_event_flow_and_gds(redpanda_service, neo4j_service):
    settings = DockerSettings(redpanda_service["bootstrap_servers"])
    client = UMEClient(settings)
    now = int(time.time())
    client.produce_event(
        Event(
            event_type=EventType.CREATE_NODE.value,
            timestamp=now,
            payload={"node_id": "n1", "attributes": {"type": "User"}},
        )
    )
    client.produce_event(
        Event(
            event_type=EventType.CREATE_NODE.value,
            timestamp=now,
            payload={"node_id": "n2", "attributes": {"type": "User"}},
        )
    )
    client.produce_event(
        Event(
            event_type=EventType.CREATE_EDGE.value,
            timestamp=now,
            node_id="n1",
            target_node_id="n2",
            label="KNOWS",
            payload={},
        )
    )
    time.sleep(1)
    events = list(client.consume_events(timeout=2))
    graph = Neo4jGraph(
        neo4j_service["uri"],
        neo4j_service["user"],
        neo4j_service["password"],
        use_gds=True,
    )
    for ev in events:
        apply_event_to_graph(ev, graph)
    pr = graph.pagerank_centrality()
    graph.close()
    client.close()
    assert set(pr) == {"n1", "n2"}

