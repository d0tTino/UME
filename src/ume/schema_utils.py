"""Utilities for validating UME events against JSON Schemas."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict, Mapping
from packaging.version import Version, InvalidVersion

from .events.contract import canonicalize_event, canonical_to_camel_dict

from jsonschema import validate, ValidationError


_ENVELOPE_SCHEMA: Dict[str, Any] | None = None
_CANONICAL_SCHEMA: Dict[str, Any] | None = None


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


def _load_canonical_schema() -> Dict[str, Any]:
    """Load JSON schema for canonical event fields."""
    global _CANONICAL_SCHEMA
    if _CANONICAL_SCHEMA is None:
        with (
            resources.files("ume.schemas")
            .joinpath("canonical_event.schema.json")
            .open("r", encoding="utf-8")
        ) as f:
            _CANONICAL_SCHEMA = json.load(f)
    return _CANONICAL_SCHEMA


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
    """Validate transport event data after normalizing to canonical contract."""
    canonical = canonicalize_event(event_data)
    validate_canonical_event(canonical)


def validate_canonical_event(canonical: Mapping[str, Any]) -> None:
    """Validate a canonical event envelope against contract and event-type schemas."""
    normalized = canonical_to_camel_dict(canonical)

    schema_version = canonical["metadata"].get("schema_version")
    if schema_version is not None:
        try:
            Version(str(schema_version))
        except InvalidVersion as exc:
            raise ValidationError("invalid schema_version") from exc

    validate(instance=normalized, schema=_load_canonical_schema())

    event_type = normalized.get("eventType")
    if not isinstance(event_type, str):
        raise ValidationError("eventType missing or not a string")
    schema = _load_schema(event_type)
    validate(instance=normalized, schema=schema)
