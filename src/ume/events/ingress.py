"""Ingress boundary for transport payload normalization and parsing."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Literal, Callable

from ..event import Event, parse_event
from ..schema_utils import validate_canonical_event
from .adapters import adapt_cli_payload, adapt_grpc_payload, adapt_kafka_payload
from .contract import canonicalize_event

IngressAdapter = Literal["default", "kafka", "grpc", "cli"]

_ADAPTERS: dict[IngressAdapter, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    "default": lambda payload: dict(payload),
    "kafka": adapt_kafka_payload,
    "grpc": adapt_grpc_payload,
    "cli": adapt_cli_payload,
}


def ingest_transport_payload(
    payload: Mapping[str, Any],
    *,
    adapter: IngressAdapter = "default",
) -> tuple[Dict[str, Any], Event]:
    """Normalize ``payload`` into canonical shape and parse an :class:`~ume.event.Event`."""

    adapted = _ADAPTERS[adapter](payload)
    canonical = canonicalize_event(adapted)
    validate_canonical_event(canonical)
    event = parse_event(canonical)
    return canonical, event


__all__ = ["IngressAdapter", "ingest_transport_payload"]
