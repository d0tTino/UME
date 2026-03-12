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
