import pytest
from jsonschema import ValidationError
from ume.schema_utils import validate_event_dict


def test_unknown_event_type_raises_validation_error():
    data = {
        "eventType": "UNKNOWN_EVENT",
        "timestamp": "2024-01-01T00:00:00Z",
    }
    with pytest.raises(ValidationError):
        validate_event_dict(data)


def test_validate_create_node_schema_success():
    data = {"eventType": "CREATE_NODE", "timestamp": "2024-01-01T00:00:00Z", "node_id": "n1", "payload": {}}
    validate_event_dict(data)


def test_validate_envelope_schema_success():
    data = {
        "schema_version": "1.0.0",
        "event": {"eventType": "CREATE_NODE", "timestamp": "2024-01-01T00:00:00Z", "node_id": "n1", "payload": {}},
    }
    validate_event_dict(data)


def test_validate_envelope_schema_bad_version():
    data = {
        "schema_version": "not-a-version",
        "event": {"eventType": "CREATE_NODE", "timestamp": "2024-01-01T00:00:00Z", "node_id": "n1", "payload": {}},
    }
    with pytest.raises(ValidationError):
        validate_event_dict(data)


def test_canonical_schema_optional_fields_valid():
    data = {
        "eventType": "UNKNOWN_EVENT",
        "timestamp": "2024-01-01T00:00:00Z",
        "eventId": "e1",
        "correlationId": "c1",
        "subjectEntity": {"id": "u1", "type": "user"},
        "sourceService": "svc",
        "payload": {},
    }
    with pytest.raises(ValidationError) as exc:
        validate_event_dict(data)
    assert "Unknown event_type" in str(exc.value)


def test_canonical_schema_invalid_payload_type(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_validate(instance: dict, schema: dict) -> None:  # type: ignore[override]
        calls.append(schema)
        if schema.get("title") == "UME Canonical Event" and not isinstance(
            instance.get("payload"), dict
        ):
            raise ValidationError("payload error")

    monkeypatch.setattr("ume.schema_utils.validate", fake_validate)

    data = {
        "eventType": "UNKNOWN_EVENT",
        "timestamp": "2024-01-01T00:00:00Z",
        "payload": "not-a-dict",
    }
    with pytest.raises(ValidationError) as exc:
        validate_event_dict(data)

    assert "payload error" in str(exc.value)
    assert any(s.get("title") == "UME Canonical Event" for s in calls)
