"""Utilities for validating UME events against JSON Schemas."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from jsonschema import ValidationError, validate
from packaging.version import InvalidVersion, Version

from .events.contract import canonical_to_camel_dict, canonicalize_event
from .schemas.contracts import load_bundle_schema, supported_contract_majors

_ENVELOPE_SCHEMAS: Dict[int, Dict[str, Any]] = {}
_CANONICAL_SCHEMAS: Dict[int, Dict[str, Any]] = {}
_SCHEMAS: Dict[tuple[int, str], Dict[str, Any]] = {}


def _major_from_schema_version(schema_version: str | None) -> int:
    if schema_version is None:
        return 1
    try:
        parsed = Version(str(schema_version))
    except InvalidVersion as exc:
        raise ValidationError("invalid schema_version") from exc

    major = parsed.major
    if major not in supported_contract_majors():
        raise ValidationError(f"unsupported schema major version: {major}")
    return major


def _load_envelope_schema(major: int) -> Dict[str, Any]:
    if major not in _ENVELOPE_SCHEMAS:
        _ENVELOPE_SCHEMAS[major] = load_bundle_schema(major, "event_envelope.schema.json")
    return _ENVELOPE_SCHEMAS[major]


def _load_canonical_schema(major: int) -> Dict[str, Any]:
    if major not in _CANONICAL_SCHEMAS:
        _CANONICAL_SCHEMAS[major] = load_bundle_schema(major, "canonical_event.schema.json")
    return _CANONICAL_SCHEMAS[major]


def _load_schema(event_type: str, major: int) -> Dict[str, Any]:
    cache_key = (major, event_type)
    if cache_key not in _SCHEMAS:
        filename = f"{event_type.lower()}.schema.json"
        try:
            _SCHEMAS[cache_key] = load_bundle_schema(major, filename)
        except FileNotFoundError as exc:
            raise ValidationError(f"Unknown event_type: {event_type}") from exc
    return _SCHEMAS[cache_key]


def validate_event_dict(event_data: Dict[str, Any]) -> None:
    """Validate transport event data after normalizing to canonical contract."""
    schema_version = event_data.get("schema_version")
    major = _major_from_schema_version(schema_version if isinstance(schema_version, str) else None)
    if "event" in event_data:
        validate(instance=event_data, schema=_load_envelope_schema(major))
    canonical = canonicalize_event(event_data)
    validate_canonical_event(canonical)


def validate_canonical_event(canonical: Mapping[str, Any]) -> None:
    """Validate a canonical event envelope against contract and event-type schemas."""
    normalized = canonical_to_camel_dict(canonical)

    schema_version = canonical["metadata"].get("schema_version")
    major = _major_from_schema_version(schema_version)

    validate(instance=normalized, schema=_load_canonical_schema(major))

    event_type = normalized.get("eventType")
    if not isinstance(event_type, str):
        raise ValidationError("eventType missing or not a string")
    schema = _load_schema(event_type, major)
    validate(instance=normalized, schema=schema)
