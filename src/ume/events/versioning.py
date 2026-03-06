"""Schema-version resolution and transformation utilities for event ingestion."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from packaging.version import Version

from .schema_resolution import resolve_active_schema


def normalize_schema_version(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def resolve_schema_version(
    canonical_event: Mapping[str, Any],
    *,
    explicit_version: str | None = None,
    fallback_version: str | None = None,
    default_version: str,
) -> str:
    """Backward-compatible wrapper around :func:`resolve_active_schema`."""
    return resolve_active_schema(
        canonical_event,
        explicit_version=explicit_version,
        fallback_version=fallback_version,
        default_version=default_version,
    ).active_version


def _major(version: str) -> int:
    return Version(version).major


def _ensure_version(canonical_event: Mapping[str, Any], version: str) -> dict[str, Any]:
    upgraded = deepcopy(dict(canonical_event))
    metadata = upgraded.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        upgraded["metadata"] = metadata
    metadata["schema_version"] = version
    return upgraded


def upgrade_event(canonical_event: Mapping[str, Any], target_version: str) -> dict[str, Any]:
    """Upgrade ``canonical_event`` into the requested schema version."""
    source_version = normalize_schema_version(
        canonical_event.get("metadata", {}).get("schema_version") if isinstance(canonical_event.get("metadata"), Mapping) else None
    ) or "1.0.0"

    source_major = _major(source_version)
    target_major = _major(target_version)
    if target_major < source_major:
        raise ValueError("target_version must be >= source version for upgrades")

    transformed = deepcopy(dict(canonical_event))
    while source_major < target_major:
        if source_major == 1:
            transformed = _upgrade_v1_to_v2(transformed)
        elif source_major == 2:
            transformed = _upgrade_v2_to_v3(transformed)
        else:
            raise ValueError(f"Unsupported upgrade path from major {source_major}")
        source_major += 1
    return _ensure_version(transformed, target_version)


def downgrade_event(canonical_event: Mapping[str, Any], target_version: str) -> dict[str, Any]:
    """Downgrade ``canonical_event`` into the requested schema version."""
    source_version = normalize_schema_version(
        canonical_event.get("metadata", {}).get("schema_version") if isinstance(canonical_event.get("metadata"), Mapping) else None
    ) or "1.0.0"

    source_major = _major(source_version)
    target_major = _major(target_version)
    if target_major > source_major:
        raise ValueError("target_version must be <= source version for downgrades")

    transformed = deepcopy(dict(canonical_event))
    while source_major > target_major:
        if source_major == 3:
            transformed = _downgrade_v3_to_v2(transformed)
        elif source_major == 2:
            transformed = _downgrade_v2_to_v1(transformed)
        else:
            raise ValueError(f"Unsupported downgrade path from major {source_major}")
        source_major -= 1
    return _ensure_version(transformed, target_version)


def _upgrade_v1_to_v2(canonical_event: Mapping[str, Any]) -> dict[str, Any]:
    transformed = deepcopy(dict(canonical_event))
    payload = transformed.setdefault("payload", {})
    if isinstance(payload, dict):
        payload.setdefault("extensions", {})
    return transformed


def _upgrade_v2_to_v3(canonical_event: Mapping[str, Any]) -> dict[str, Any]:
    transformed = deepcopy(dict(canonical_event))
    metadata = transformed.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata.setdefault("event_id", "replay-generated")
        metadata.setdefault("source", "replay")
    return transformed


def _downgrade_v3_to_v2(canonical_event: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(dict(canonical_event))


def _downgrade_v2_to_v1(canonical_event: Mapping[str, Any]) -> dict[str, Any]:
    transformed = deepcopy(dict(canonical_event))
    payload = transformed.get("payload")
    if isinstance(payload, dict):
        payload.pop("extensions", None)
    return transformed
