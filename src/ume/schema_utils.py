"""Utilities for validating UME events against JSON Schemas."""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict

from jsonschema import validate, ValidationError  # type: ignore


_SCHEMAS: Dict[str, Dict[str, Any]] = {}


def _load_schema(event_type: str) -> Dict[str, Any]:
    """Load JSON schema for a specific event type."""
    if event_type not in _SCHEMAS:
        filename = f"{event_type.lower()}.schema.json"
        with resources.files("ume.schemas").joinpath(filename).open("r", encoding="utf-8") as f:
            _SCHEMAS[event_type] = json.load(f)
    return _SCHEMAS[event_type]


def validate_event_dict(event_data: Dict[str, Any]) -> None:
    """Validate a raw event dictionary against its JSON schema."""
    event_type = event_data.get("event_type")
    if not isinstance(event_type, str):
        raise ValidationError("event_type missing or not a string")
    schema = _load_schema(event_type)
    validate(instance=event_data, schema=schema)

