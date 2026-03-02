from ume.graph_routes import EventRequest


def test_event_request_accepts_legacy_aliases() -> None:
    req = EventRequest(
        eventType="CREATE_NODE",
        eventId="e-1",
        timestamp=1700000000,
        sourceService="api",
        node_id="n1",
        payload={"node_id": "n1", "attributes": {}},
    )

    event = req.to_ingress_dict()
    assert event["event_type"] == "CREATE_NODE"
    assert event["event_id"] == "e-1"
    assert event["source"] == "api"


def test_event_request_accepts_canonical_envelope_keys() -> None:
    req = EventRequest(
        event_type="CREATE_EDGE",
        event_id="e-2",
        timestamp=1700000001,
        source="api",
        node_id="n1",
        target_node_id="n2",
        label="RELATES_TO",
        schema_version="3.0.0",
        payload={"attributes": {}},
    )

    assert req.to_ingress_dict()["schema_version"] == "3.0.0"
