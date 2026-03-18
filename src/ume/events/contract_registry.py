from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..schemas.contracts import load_bundle_manifest, load_bundle_schema

_RESERVED_SCHEMAS = {"canonical_event.schema.json", "event_envelope.schema.json"}
_EVENT_CONTRACT_MAJOR = 3


@dataclass(frozen=True)
class EventContract:
    event_type: str
    schema_name: str
    schema: dict[str, Any]

    @property
    def required_fields(self) -> frozenset[str]:
        required = self.schema.get("required", [])
        return frozenset(field for field in required if isinstance(field, str))

    @property
    def payload_schema(self) -> dict[str, Any]:
        payload = self.schema.get("properties", {}).get("payload")
        return payload if isinstance(payload, dict) else {}

    @property
    def payload_required_fields(self) -> frozenset[str]:
        required = self.payload_schema.get("required", [])
        return frozenset(field for field in required if isinstance(field, str))

    @property
    def graph_required_fields(self) -> frozenset[str]:
        return frozenset(
            field for field in self.required_fields if field in {"node_id", "target_node_id", "label"}
        )


def load_event_contracts(major: int = _EVENT_CONTRACT_MAJOR) -> dict[str, EventContract]:
    manifest = load_bundle_manifest(major)
    contracts: dict[str, EventContract] = {}
    for schema_name in manifest.get("schemas", []):
        if schema_name in _RESERVED_SCHEMAS:
            continue
        schema = load_bundle_schema(major, schema_name)
        event_type = schema.get("title")
        if not isinstance(event_type, str) or not event_type:
            raise ValueError(f"Schema {schema_name} is missing a string title")
        contracts[event_type] = EventContract(
            event_type=event_type,
            schema_name=schema_name,
            schema=schema,
        )
    return contracts


def contract_event_types(major: int = _EVENT_CONTRACT_MAJOR) -> frozenset[str]:
    return frozenset(load_event_contracts(major))


def taxonomy_event_types() -> frozenset[str]:
    from .types import EventType

    return frozenset(event_type.value for event_type in EventType)


def missing_contract_event_types(major: int = _EVENT_CONTRACT_MAJOR) -> frozenset[str]:
    return taxonomy_event_types() - contract_event_types(major)


__all__ = [
    "EventContract",
    "contract_event_types",
    "load_event_contracts",
    "missing_contract_event_types",
    "taxonomy_event_types",
]
