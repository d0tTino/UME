"""Utilities for validating UME events against JSON Schemas."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict
from packaging.version import Version, InvalidVersion

from jsonschema import validate, ValidationError


_ENVELOPE_SCHEMA: Dict[str, Any] | None = None


_SCHEMAS: Dict[str, Dict[str, Any]] = {}


def _load_envelope_schema() -> Dict[str, Any]:
    """Load JSON schema for the event envelope."""
    global _ENVELOPE_SCHEMA
    if _ENVELOPE_SCHEMA is None:
        with (
            resources.files("ume.schemas")
            .joinpath("event_envelope.schema.json")
            .open("r", encoding="utf-8")
        ) as f:
            _ENVELOPE_SCHEMA = json.load(f)
    return _ENVELOPE_SCHEMA


def _load_schema(event_type: str) -> Dict[str, Any]:
    """Load JSON schema for a specific event type."""
    if event_type not in _SCHEMAS:
        filename = f"{event_type.lower()}.schema.json"
        try:
            with (
                resources.files("ume.schemas")
                .joinpath(filename)
                .open("r", encoding="utf-8") as f
            ):
                _SCHEMAS[event_type] = json.load(f)
        except FileNotFoundError as exc:
            raise ValidationError(f"Unknown event_type: {event_type}") from exc
    return _SCHEMAS[event_type]


def validate_event_dict(event_data: Dict[str, Any]) -> None:
    """Validate a raw event dictionary or envelope against its JSON schema."""
    if "event" in event_data and "schema_version" in event_data:
        validate(instance=event_data, schema=_load_envelope_schema())
        version = event_data["schema_version"]
        try:
            Version(version)
        except InvalidVersion as exc:
            raise ValidationError("invalid schema_version") from exc
        event_data = event_data["event"]

    event_type = event_data.get("event_type")
    if not isinstance(event_type, str):
        raise ValidationError("event_type missing or not a string")
    schema = _load_schema(event_type)
    validate(instance=event_data, schema=schema)
