from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CAPABILITY_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class CapabilitySchema:
    """Versioned capability declaration and negotiation payload."""

    domain: Literal["graph", "vector", "integration"]
    backend: str
    declared: tuple[str, ...]
    supported: tuple[str, ...]
    fallbacks: dict[str, str] = field(default_factory=dict)
    schema_version: str = CAPABILITY_SCHEMA_VERSION
    field_versions: dict[str, str] = field(
        default_factory=lambda: {
            "domain": "1.0",
            "backend": "1.0",
            "declared": "1.0",
            "supported": "1.0",
            "fallbacks": "1.0",
        }
    )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "field_versions": dict(self.field_versions),
            "domain": self.domain,
            "backend": self.backend,
            "declared": list(self.declared),
            "supported": list(self.supported),
            "fallbacks": dict(self.fallbacks),
        }


def build_capability_schema(
    *,
    domain: Literal["graph", "vector", "integration"],
    backend: str,
    declared: frozenset[str],
    supported: frozenset[str] | None = None,
    fallbacks: dict[str, str] | None = None,
) -> CapabilitySchema:
    supported_capabilities = declared if supported is None else supported
    return CapabilitySchema(
        domain=domain,
        backend=backend.lower(),
        declared=tuple(sorted(declared)),
        supported=tuple(sorted(supported_capabilities)),
        fallbacks=dict(fallbacks or {}),
    )
