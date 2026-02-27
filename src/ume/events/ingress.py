"""Ingress boundary for transport payload normalization and parsing."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Literal

from ..event import Event, parse_event
from ..schema_utils import validate_canonical_event
from .contract import canonicalize_event

IngressAdapter = Literal["default", "kafka", "grpc", "cli"]


def _legacy_transport_adapter(
    payload: Mapping[str, Any],
    *,
    adapter: IngressAdapter,
) -> Dict[str, Any]:
    normalized = dict(payload)

    if adapter in {"kafka", "cli"}:
        if "nodeId" in normalized and "node_id" not in normalized:
            normalized["node_id"] = normalized["nodeId"]
        if "targetNodeId" in normalized and "target_node_id" not in normalized:
            normalized["target_node_id"] = normalized["targetNodeId"]

    if adapter == "grpc":
        if "sourceService" in normalized and "source" not in normalized:
            normalized["source"] = normalized["sourceService"]
        if "schemaVersion" in normalized and "schema_version" not in normalized:
            normalized["schema_version"] = normalized["schemaVersion"]

    return normalized


def ingest_transport_payload(
    payload: Mapping[str, Any],
    *,
    adapter: IngressAdapter = "default",
) -> tuple[Dict[str, Any], Event]:
    """Normalize ``payload`` into canonical shape and parse an :class:`~ume.event.Event`."""

    adapted = _legacy_transport_adapter(deepcopy(payload), adapter=adapter)
    canonical = canonicalize_event(adapted)
    validate_canonical_event(canonical)
    event = parse_event(canonical)
    return canonical, event


__all__ = ["IngressAdapter", "ingest_transport_payload"]

