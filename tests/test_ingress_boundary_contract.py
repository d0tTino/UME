from ume.events.ingress import ingest_transport_payload


def test_ingress_paths_produce_identical_canonical_output() -> None:
    kafka_payload = {
        "eventId": "evt-1",
        "eventType": "CREATE_EDGE",
        "timestamp": 1700000000,
        "nodeId": "n1",
        "targetNodeId": "n2",
        "label": "RELATES_TO",
        "payload": {"weight": 1},
        "sourceService": "producer",
        "schemaVersion": "1.0.0",
    }
    grpc_payload = {
        "eventId": "evt-1",
        "eventType": "CREATE_EDGE",
        "timestamp": 1700000000,
        "node_id": "n1",
        "target_node_id": "n2",
        "label": "RELATES_TO",
        "payload": {"weight": 1},
        "sourceService": "producer",
        "schemaVersion": "1.0.0",
    }
    cli_payload = {
        "event_id": "evt-1",
        "event_type": "CREATE_EDGE",
        "timestamp": 1700000000,
        "node_id": "n1",
        "target_node_id": "n2",
        "label": "RELATES_TO",
        "payload": {"weight": 1},
        "source": "producer",
        "schema_version": "1.0.0",
    }

    kafka_canonical, kafka_event = ingest_transport_payload(kafka_payload, adapter="kafka")
    grpc_canonical, grpc_event = ingest_transport_payload(grpc_payload, adapter="grpc")
    cli_canonical, cli_event = ingest_transport_payload(cli_payload, adapter="cli")

    assert kafka_canonical == grpc_canonical == cli_canonical
    assert kafka_event == grpc_event == cli_event
