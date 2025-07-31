import pytest
from jsonschema import ValidationError
from ume.schema_utils import validate_event_dict


VALID_BASE_EVENT = {
    "eventType": "CREATE_NODE",
    "timestamp": "2024-01-01T00:00:00Z",
    "node_id": "n1",
    "payload": {},
}


def test_validate_event_optional_fields_pass():
    event = {
        **VALID_BASE_EVENT,
        "correlationId": "corr-1",
        "subjectEntity": {"id": "u1", "type": "user"},
    }
    validate_event_dict(event)


@pytest.mark.parametrize(
    "bad_event",
    [
        {**VALID_BASE_EVENT, "correlationId": 1},
        {**VALID_BASE_EVENT, "subjectEntity": "foo"},
        {**VALID_BASE_EVENT, "subjectEntity": {"id": "u1"}},
        {**VALID_BASE_EVENT, "subjectEntity": {"id": 1, "type": "user"}},
    ],
)
def test_validate_event_optional_fields_fail(bad_event):
    with pytest.raises(ValidationError):
        validate_event_dict(bad_event)
