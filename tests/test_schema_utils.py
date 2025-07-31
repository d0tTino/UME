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
