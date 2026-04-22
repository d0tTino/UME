"""Kernel policy interfaces and compatibility exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict

from .events import Event
from ..events.ingress import IngressAdapter

if TYPE_CHECKING:
    from .graph_adapter import IGraphAdapter


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    QUARANTINE = "QUARANTINE"
    REDACTED = "REDACTED"


@dataclass
class PolicyContext:
    source: str
    adapter: IngressAdapter = "default"
    raw_payload: bytes | None = None
    transport_data: Dict[str, Any] | None = None
    canonical_event: Dict[str, Any] | None = None
    original_event: Event | None = None
    effective_event: Event | None = None
    graph_read_view: Dict[str, Any] | None = None
    graph_adapter: IGraphAdapter | None = None
    redacted: bool = False
    producer_auth: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def event_payload(self) -> Dict[str, Any]:
        if self.canonical_event is None:
            return {}
        payload = self.canonical_event.get("payload")
        if isinstance(payload, dict):
            return payload
        return {}

    @property
    def event(self) -> Event | None:
        return self.effective_event

    @property
    def policy_input(self) -> Dict[str, Any]:
        event = self.effective_event
        actor: Dict[str, Any] = {}
        if event is not None and isinstance(event.subject_entity, dict):
            actor = dict(event.subject_entity)
        if not actor:
            user_id = self.event_payload.get("user_id")
            if user_id is not None:
                actor = {"id": str(user_id), "type": "user"}

        event_doc: Dict[str, Any] = {}
        if event is not None:
            event_doc = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "node_id": event.node_id,
                "target_node_id": event.target_node_id,
                "label": event.label,
                "payload": event.payload,
                "correlation_id": event.correlation_id,
                "schema_version": event.schema_version,
                "producer_id": event.producer_id,
                "tenant": event.tenant,
                "producer_signature": event.producer_signature,
            }

        source_doc: Dict[str, Any] = {"transport": self.source}
        if event is not None and event.source_service:
            source_doc["service"] = event.source_service

        return {
            "event": event_doc,
            "graph": self.graph_read_view or {},
            "actor": actor,
            "source": source_doc,
            "producer": {
                "authenticated": bool(self.producer_auth.get("authenticated", False)),
                "authorized": bool(self.producer_auth.get("authorized", False)),
                "method": self.producer_auth.get("method"),
                "claims": self.producer_auth.get("claims", {}),
            },
            "metadata": {
                "redacted": self.redacted,
                "canonical_metadata": (self.canonical_event or {}).get("metadata", {}),
            },
        }


def build_default_policy_pipeline(*args: Any, **kwargs: Any):
    return import_module("ume.policy.pipeline").build_default_policy_pipeline(*args, **kwargs)


def __getattr__(name: str):
    if name == "PolicyPipeline":
        return import_module("ume.policy.pipeline").PolicyPipeline
    raise AttributeError(name)


PolicyPipeline: Any

__all__ = [
    "PolicyContext",
    "PolicyDecision",
    "PolicyPipeline",
    "build_default_policy_pipeline",
]
