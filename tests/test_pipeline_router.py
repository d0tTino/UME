from ume.pipeline.router import RouterConfig, route_event


def _canonical_event(
    *,
    event_type: str,
    node_id: str | None = None,
    target_node_id: str | None = None,
    label: str | None = None,
    type_family: str | None = None,
    schema_version: str = "v1",
    policy_result: str | None = None,
    schema_topic: str | None = None,
) -> dict:
    metadata: dict = {
        "event_type": event_type,
        "timestamp": 1,
        "schema_version": schema_version,
    }
    if type_family is not None:
        metadata["type_family"] = type_family
    if policy_result is not None:
        metadata["policy_result"] = policy_result
    if schema_topic is not None:
        metadata["schema"] = {"topic": schema_topic}

    return {
        "metadata": metadata,
        "graph": {
            "node_id": node_id,
            "target_node_id": target_node_id,
            "label": label,
        },
        "payload": {},
    }


def test_routes_node_family_to_node_topic():
    config = RouterConfig(
        node_topic="ume_nodes",
        edge_topic="ume_edges",
        default_topic="ume_misc",
        dead_letter_topic="ume_dlq",
    )

    decision = route_event(
        _canonical_event(event_type="CREATE_NODE", node_id="n1"),
        config,
    )

    assert decision.topic == "ume_nodes"
    assert decision.family == "node"


def test_routes_edge_family_to_edge_topic():
    config = RouterConfig(
        node_topic="ume_nodes",
        edge_topic="ume_edges",
        default_topic="ume_misc",
        dead_letter_topic="ume_dlq",
    )

    decision = route_event(
        _canonical_event(
            event_type="CREATE_EDGE",
            node_id="a",
            target_node_id="b",
            label="LIKES",
        ),
        config,
    )

    assert decision.topic == "ume_edges"
    assert decision.family == "edge"


def test_routes_unknown_family_to_fallback_topic():
    config = RouterConfig(
        node_topic="ume_nodes",
        edge_topic="ume_edges",
        default_topic="ume_misc",
        dead_letter_topic="ume_dlq",
    )

    decision = route_event(_canonical_event(event_type="UNKNOWN_EVENT"), config)

    assert decision.topic == "ume_misc"
    assert decision.family == "unknown"


def test_routes_custom_schema_topic_override():
    config = RouterConfig(
        node_topic="ume_nodes",
        edge_topic="ume_edges",
        default_topic="ume_misc",
        dead_letter_topic="ume_dlq",
    )

    decision = route_event(
        _canonical_event(event_type="TENANT_AUDIT", schema_topic="tenant-audit-topic"),
        config,
    )

    assert decision.topic == "tenant-audit-topic"
    assert decision.reason == "schema_topic"


def test_routes_policy_deny_to_dead_letter():
    config = RouterConfig(
        node_topic="ume_nodes",
        edge_topic="ume_edges",
        default_topic="ume_misc",
        dead_letter_topic="ume_dlq",
    )

    decision = route_event(
        _canonical_event(
            event_type="CREATE_NODE",
            node_id="n1",
            policy_result="DENIED",
        ),
        config,
    )

    assert decision.topic == "ume_dlq"
    assert decision.reason == "policy_denied"
