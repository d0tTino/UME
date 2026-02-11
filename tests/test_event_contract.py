from __future__ import annotations

import pytest

pytest.importorskip("google.protobuf.json_format")

from ume.events.contract import canonicalize_event, canonical_to_camel_dict
from ume.services.ingest import dict_to_envelope, envelope_to_event_dict
from ume.schema_utils import validate_event_dict


def test_legacy_shapes_normalize_to_same_canonical_form() -> None:
    expected = {
        "metadata": {
            "event_id": "e-1",
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "schema_version": "1.0.0",
            "source": "demo",
            "correlation_ids": {"correlation_id": "c-1"},
            "subject_entity": {"id": "u1", "type": "user"},
        },
        "graph": {"node_id": "n1", "target_node_id": None, "label": None},
        "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
    }

    legacy_shapes = [
        {
            "eventId": "e-1",
            "eventType": "CREATE_NODE",
            "timestamp": 1,
            "schema_version": "1.0.0",
            "sourceService": "demo",
            "correlationId": "c-1",
            "subjectEntity": {"id": "u1", "type": "user"},
            "node_id": "n1",
            "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
        },
        {
            "event_id": "e-1",
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "schema_version": "1.0.0",
            "source": "demo",
            "correlation_id": "c-1",
            "subject_entity": {"id": "u1", "type": "user"},
            "node_id": "n1",
            "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
        },
        {
            "schemaVersion": "1.0.0",
            "event": {
                "eventId": "e-1",
                "eventType": "CREATE_NODE",
                "timestamp": 1,
                "sourceService": "demo",
                "correlationId": "c-1",
                "subjectEntity": {"id": "u1", "type": "user"},
                "nodeId": "n1",
                "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
            },
        },
    ]

    for shape in legacy_shapes:
        assert canonicalize_event(shape) == expected


def test_json_schema_and_protobuf_converters_accept_canonicalized_shape() -> None:
    event = {
        "event_type": "CREATE_EDGE",
        "event_id": "e-2",
        "timestamp": 2,
        "schema_version": "1.0.0",
        "node_id": "n1",
        "target_node_id": "n2",
        "label": "RELATES_TO",
        "payload": {},
    }

    canonical = canonicalize_event(event)
    transport = canonical_to_camel_dict(canonical)

    validate_event_dict(transport)
    envelope = dict_to_envelope(event)
    round_trip = envelope_to_event_dict(envelope)
    assert canonicalize_event(round_trip) == canonical
