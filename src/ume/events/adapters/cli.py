from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def adapt_cli_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(deepcopy(payload))
    if "nodeId" in normalized and "node_id" not in normalized:
        normalized["node_id"] = normalized["nodeId"]
    if "targetNodeId" in normalized and "target_node_id" not in normalized:
        normalized["target_node_id"] = normalized["targetNodeId"]
    return normalized
