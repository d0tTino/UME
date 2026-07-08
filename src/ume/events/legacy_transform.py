from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def apply_legacy_transform(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Upgrade legacy transport/event shapes to the external ingress contract.

    Boundary marker: this is the only backward-compatibility transform entrypoint.
    It normalizes legacy inputs into the authoritative external producer contract;
    the next hop must be ``ume.events.contract.canonicalize_event(...)``, which is
    the one canonical transform into parser-ready canonical form. All new ingress
    code should provide already-compliant external payloads and skip this module.
    """

    normalized = dict(deepcopy(payload))

    if "event" in normalized and isinstance(normalized["event"], Mapping):
        nested = dict(deepcopy(normalized["event"]))
        if "schemaVersion" in normalized and "schemaVersion" not in nested:
            nested["schemaVersion"] = normalized["schemaVersion"]
        if "schema_version" in normalized and "schemaVersion" not in nested:
            nested["schemaVersion"] = normalized["schema_version"]
        normalized = nested

    # Promote snake_case historical fields to external camelCase contract keys.
    if "event_id" in normalized and "eventId" not in normalized:
        normalized["eventId"] = normalized["event_id"]
    normalized.pop("event_id", None)
    if "event_type" in normalized and "eventType" not in normalized:
        normalized["eventType"] = normalized["event_type"]
    normalized.pop("event_type", None)
    if "schema_version" in normalized and "schemaVersion" not in normalized:
        normalized["schemaVersion"] = normalized["schema_version"]
    normalized.pop("schema_version", None)
    if "source" in normalized and "sourceService" not in normalized:
        normalized["sourceService"] = normalized["source"]
    normalized.pop("source", None)
    if "producer_signature" in normalized and "signature" not in normalized:
        normalized["signature"] = normalized["producer_signature"]
    normalized.pop("producer_signature", None)
    if "correlation_id" in normalized and "correlationId" not in normalized:
        normalized["correlationId"] = normalized["correlation_id"]
    normalized.pop("correlation_id", None)
    if "subject_entity" in normalized and "subjectEntity" not in normalized:
        normalized["subjectEntity"] = normalized["subject_entity"]
    normalized.pop("subject_entity", None)

    # Promote graph aliases.
    if "nodeId" in normalized and "node_id" not in normalized:
        normalized["node_id"] = normalized["nodeId"]
    if "targetNodeId" in normalized and "target_node_id" not in normalized:
        normalized["target_node_id"] = normalized["targetNodeId"]

    return normalized
