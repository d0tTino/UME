from __future__ import annotations

import pytest

pytest.importorskip("google.protobuf.json_format")

from ume.events.contract import canonical_to_camel_dict, canonicalize_event
from ume.events.versioning import downgrade_event, upgrade_event
from ume.schema_utils import validate_canonical_event, validate_event_dict
from ume.schemas.contracts import load_bundle_schema, supported_contract_majors
from ume.services.ingest import dict_to_envelope, envelope_to_event_dict


def _canonical(version: str = "1.0.0") -> dict[str, object]:
    return {
        "metadata": {
            "event_id": "e-1",
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "schema_version": version,
            "source": "demo",
            "producer_id": None,
            "tenant": None,
            "producer_signature": None,
            "correlation_ids": {"correlation_id": "c-1"},
            "subject_entity": {"id": "u1", "type": "user"},
        },
        "graph": {"node_id": "n1", "target_node_id": None, "label": None},
        "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
    }


def test_legacy_shapes_normalize_to_same_canonical_form() -> None:
    expected = _canonical()

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


def test_contract_bundles_exist_and_can_be_loaded() -> None:
    for major in supported_contract_majors():
        bundle = load_bundle_schema(major, "bundle.json")
        assert bundle["contract_version"].startswith(f"{major}.")
        for schema_name in bundle["schemas"]:
            schema = load_bundle_schema(major, schema_name)
            assert schema.get("type") == "object"


def test_contract_required_fields_only_add_within_next_major() -> None:
    previous_required: set[str] | None = None
    for major in supported_contract_majors():
        current_required = set(load_bundle_schema(major, "canonical_event.schema.json").get("required", []))
        if previous_required is not None and major in (2,):
            # v2 is additive and must retain v1 requirements.
            assert previous_required.issubset(current_required)
        previous_required = current_required


def test_upgrade_and_downgrade_transformers_support_replay_compatibility() -> None:
    v1 = _canonical("1.0.0")
    v3 = upgrade_event(v1, "3.0.0")
    validate_canonical_event(v3)
    assert v3["metadata"]["schema_version"] == "3.0.0"

    back_to_v1 = downgrade_event(v3, "1.0.0")
    validate_canonical_event(back_to_v1)
    assert back_to_v1["metadata"]["schema_version"] == "1.0.0"


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


def test_v3_breaking_fields_require_transform_when_missing() -> None:
    canonical = _canonical("2.0.0")
    canonical["metadata"].pop("event_id")
    canonical["metadata"].pop("source")

    upgraded = upgrade_event(canonical, "3.0.0")
    validate_canonical_event(upgraded)
    assert upgraded["metadata"]["event_id"] == "replay-generated"
    assert upgraded["metadata"]["source"] == "replay"
