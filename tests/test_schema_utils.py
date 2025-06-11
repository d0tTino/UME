import pytest
from jsonschema import ValidationError
from ume.schema_utils import validate_event_dict


def test_unknown_event_type_raises_validation_error():
    data = {
        "event_type": "UNKNOWN_EVENT",
        "timestamp": 1,
    }
    with pytest.raises(ValidationError):
        validate_event_dict(data)


def test_validate_create_node_schema_success():
    data = {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {}}
    validate_event_dict(data)
