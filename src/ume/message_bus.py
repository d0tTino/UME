from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class MessageEnvelope:
    """JSON-RPC envelope implementing the OVON schema."""

    content: str
    id: str | int | None = None
    jsonrpc: str = "2.0"
    ovon: str = "0.1"
    meta: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        """Return this envelope as a JSON serializable dictionary."""
        return {
            "jsonrpc": self.jsonrpc,
            "ovon": self.ovon,
            "id": self.id,
            "content": self.content,
            "meta": self.meta or {},
        }
