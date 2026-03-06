from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def adapt_grpc_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(deepcopy(payload.get("event", payload)))
    if "sourceService" in normalized and "source" not in normalized:
        normalized["source"] = normalized["sourceService"]
    if "schemaVersion" in normalized and "schema_version" not in normalized:
        normalized["schema_version"] = normalized["schemaVersion"]
    if "schema_version" in payload and "schema_version" not in normalized:
        normalized["schema_version"] = payload["schema_version"]
    return normalized
