from ume.models import CalendarLayer, create_calendar_layer
from ume.models.calendar_layer import SCHEMA_VERSION
import uuid


def test_create_calendar_layer_generates_id() -> None:
    layer = create_calendar_layer("Work", "blue")
    assert isinstance(layer, CalendarLayer)
    assert layer.layer_name == "Work"
    assert layer.color == "blue"
    assert layer.schema_version == SCHEMA_VERSION
    uuid.UUID(layer.layer_id)


def test_create_calendar_layer_with_provided_id() -> None:
    custom_id = "123"
    layer = create_calendar_layer("Personal", "red", layer_id=custom_id)
    assert layer.layer_id == custom_id
    assert layer.schema_version == SCHEMA_VERSION
