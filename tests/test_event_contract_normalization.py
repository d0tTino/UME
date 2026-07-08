from ume.events.contract import canonical_to_camel_dict, canonicalize_event
import pytest


def test_external_contract_round_trip_preserves_fields() -> None:
    external = {
        "eventId": "e-1",
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "schemaVersion": "3.0.0",
        "sourceService": "demo",
        "correlationId": "c-1",
        "subjectEntity": {"id": "u1", "type": "user"},
        "node_id": "n1",
        "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
    }

    canonical = canonicalize_event(external)
    assert canonical_to_camel_dict(canonical) == external


def test_external_contract_round_trip_edge_event() -> None:
    external = {
        "eventType": "CREATE_EDGE",
        "timestamp": "2024-01-01T00:00:00Z",
        "eventId": "edge-1",
        "sourceService": "demo",
        "node_id": "a",
        "target_node_id": "b",
        "label": "LINKS_TO",
    }

    canonical = canonicalize_event(external)
    assert canonical_to_camel_dict(canonical) == {**external, "payload": {}}


def test_event_envelope_is_rejected() -> None:
    with pytest.raises(ValueError, match="legacy_transform"):
        canonicalize_event(
            {
                "schemaVersion": "3.0.0",
                "event": {"eventType": "CREATE_NODE", "timestamp": 1},
            }
        )


def test_legacy_transform_is_required_before_canonicalize_for_deprecated_aliases() -> None:
    legacy = {
        "event_id": "legacy-1",
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "schema_version": "2.0.0",
        "source": "old-service",
        "producer_signature": "sig",
        "correlation_id": "corr",
        "subject_entity": {"id": "u1", "type": "User"},
        "nodeId": "n1",
        "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
    }

    with pytest.raises(ValueError, match="legacy_transform"):
        canonicalize_event(legacy)

    from ume.events.legacy_transform import apply_legacy_transform

    external = apply_legacy_transform(legacy)
    assert external == {
        "eventId": "legacy-1",
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "schemaVersion": "2.0.0",
        "sourceService": "old-service",
        "signature": "sig",
        "correlationId": "corr",
        "subjectEntity": {"id": "u1", "type": "User"},
        "nodeId": "n1",
        "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
        "node_id": "n1",
    }
    canonical = canonicalize_event(external)
    assert canonical["metadata"]["event_id"] == "legacy-1"
    assert canonical["metadata"]["event_type"] == "CREATE_NODE"
    assert canonical["metadata"]["schema_version"] == "2.0.0"
    assert canonical["metadata"]["source"] == "old-service"
    assert canonical["metadata"]["producer_signature"] == "sig"
    assert canonical["metadata"]["correlation_ids"] == {"correlation_id": "corr"}
    assert canonical["metadata"]["subject_entity"] == {"id": "u1", "type": "User"}
    assert canonical["graph"]["node_id"] == "n1"


def test_parse_event_rejects_external_contract_until_canonicalized() -> None:
    from ume.kernel.events import EventError, parse_event

    external = {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n1",
        "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
    }

    with pytest.raises(EventError, match="parse_event expects canonicalized data"):
        parse_event(external)

    event = parse_event(canonicalize_event(external))
    assert event.event_type == "CREATE_NODE"
    assert event.node_id == "n1"
