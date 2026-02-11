import asyncio
import json

from ume.pipeline.stream_processor import build_app


def _encoded(event: dict) -> bytes:
    return json.dumps(event).encode()


def _topic_map(agent_fun) -> dict[str, object]:
    assert agent_fun.__closure__ is not None
    for cell in agent_fun.__closure__:
        value = cell.cell_contents
        if isinstance(value, dict) and value and all(
            isinstance(k, str) and hasattr(v, "send") for k, v in value.items()
        ):
            return value
    raise AssertionError("topic map closure not found")


def test_stream_routing():
    app = build_app("kafka://dummy")
    agent = next(iter(app.agents.values()))

    topic_map = _topic_map(agent.fun)
    edge_topic = topic_map["ume_edges"]
    node_topic = topic_map["ume_nodes"]

    edge_msgs: list[bytes] = []
    node_msgs: list[bytes] = []

    async def fake_edge_send(*, value: bytes) -> None:
        edge_msgs.append(value)

    async def fake_node_send(*, value: bytes) -> None:
        node_msgs.append(value)

    edge_topic.send = fake_edge_send
    node_topic.send = fake_node_send

    edge_event = _encoded(
        {
            "event_type": "CREATE_EDGE",
            "timestamp": 1,
            "node_id": "a",
            "target_node_id": "b",
            "label": "L",
        }
    )
    node_event = _encoded(
        {
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "node_id": "n1",
            "payload": {"attributes": {"type": "UserMemory"}, "node_id": "n1"},
        }
    )

    async def run() -> None:
        async def agen():
            for data in [edge_event, node_event]:
                yield data

        await agent.fun(agen())

    asyncio.run(run())

    assert edge_msgs == [edge_event]
    assert node_msgs == [node_event]
