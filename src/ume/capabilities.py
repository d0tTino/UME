from __future__ import annotations

from dataclasses import dataclass, field


TRANSACTIONAL_CAPABILITY = "transactional"
BULK_WRITE_CAPABILITY = "bulk_write"
NATIVE_ACL_CAPABILITY = "native_acl"
VECTOR_SIMILARITY_CAPABILITY = "vector_similarity"


class CapabilityNotSupportedError(RuntimeError):
    """Raised when attempting to use an unsupported backend capability."""


@dataclass(frozen=True)
class CapabilityNegotiation:
    """Represents supported capabilities and fallback behavior."""

    supported: frozenset[str] = field(default_factory=frozenset)
    fallbacks: dict[str, str] = field(default_factory=dict)

    def supports(self, capability: str) -> bool:
        return capability in self.supported

    def require(self, capability: str) -> None:
        if self.supports(capability):
            return
        fallback = self.fallbacks.get(capability)
        if fallback:
            raise CapabilityNotSupportedError(
                f"Capability '{capability}' is unavailable; fallback: {fallback}"
            )
        raise CapabilityNotSupportedError(f"Capability '{capability}' is unavailable")

    def as_dict(self) -> dict[str, object]:
        return {
            "supported": sorted(self.supported),
            "fallbacks": dict(self.fallbacks),
        }
