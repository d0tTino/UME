import asyncio
import json

from ume.pipeline.stream_processor import build_app


def _encoded(event: dict) -> bytes:
    return json.dumps(event).encode()


def _topic_map(agent_fun) -> dict[str, object]:
    assert agent_fun.__closure__ is not None
    for cell in agent_fun.__closure__:
        value = cell.cell_contents
        if (
            isinstance(value, dict)
            and value
            and all(isinstance(k, str) and hasattr(v, "send") for k, v in value.items())
        ):
            return value
    raise AssertionError("topic map closure not found")


def _run_stream_once(raw_payload: bytes) -> tuple[str, dict]:
    app = build_app("kafka://dummy")
    agent = next(iter(app.agents.values()))
    topic_map = _topic_map(agent.fun)

    published: dict[str, list[dict]] = {name: [] for name in topic_map}

    for topic_name, topic in topic_map.items():

        async def fake_send(*, value: bytes, _topic_name: str = topic_name) -> None:
            published[_topic_name].append(json.loads(value.decode("utf-8")))

        topic.send = fake_send

    async def run() -> None:
        async def agen():
            yield raw_payload

        await agent.fun(agen())

    asyncio.run(run())

    sent = [
        (topic_name, messages[0])
        for topic_name, messages in published.items()
        if messages
    ]
    assert len(sent) == 1
    return sent[0]


def test_stream_routing_valid_event_payload_and_metadata():
    topic, payload = _run_stream_once(
        _encoded(
            {
                "event_type": "CREATE_EDGE",
                "timestamp": 1,
                "node_id": "a",
                "target_node_id": "b",
                "label": "L",
            }
        )
    )

    assert topic == "ume_edges"
    assert payload["metadata"]["policy_result"] == "applied"
    assert payload["metadata"]["schema_version"] == "unknown"
    assert payload["metadata"]["type_family"] == "edge"
    assert payload["metadata"]["routing"] == {
        "topic": "ume_edges",
        "reason": "edge_family",
        "family": "edge",
        "schema_version": None,
        "policy_result": "applied",
    }


def test_stream_routing_policy_reject_to_dead_letter_with_envelope():
    topic, payload = _run_stream_once(
        _encoded(
            {
                "event_type": "CREATE_NODE",
                "timestamp": 1,
                "node_id": "n1",
                "payload": {
                    "attributes": {"type": "UserMemory"},
                    "node_id": "n1",
                    "user_id": "u1",
                    "scope": "private",
                },
            }
        )
    )

    assert topic == "ume-dead-letter-events"
    assert payload["metadata"]["policy_result"] == "rejected"
    assert payload["metadata"]["schema_version"] == "unknown"
    assert payload["metadata"]["type_family"] == "node"
    assert payload["metadata"]["routing"]["topic"] == "ume-dead-letter-events"


def test_stream_routing_quarantine_to_dead_letter_with_dlq_payload():
    topic, payload = _run_stream_once(
        _encoded(
            {
                "event_type": "CREATE_NODE",
                "timestamp": 1,
                "node_id": "n1",
                "payload": "invalid",
            }
        )
    )

    assert topic == "ume-dead-letter-events"
    assert payload["metadata"]["policy_result"] == "quarantined"
    assert payload["metadata"]["schema_version"] == "unknown"
    assert payload["metadata"]["type_family"] == "unknown"
    assert payload["dlq"]["stage"] == "validate"


def test_stream_routing_malformed_input_to_dead_letter_with_dlq_payload():
    topic, payload = _run_stream_once(b"not-json")

    assert topic == "ume-dead-letter-events"
    assert payload["metadata"]["policy_result"] == "rejected"
    assert payload["metadata"]["schema_version"] == "unknown"
    assert payload["metadata"]["routing"]["reason"] == "policy_denied"
    assert payload["dlq"] == {
        "stage": "decode",
        "reason": "malformed_json",
        "details": {"raw_payload_present": True},
    }
