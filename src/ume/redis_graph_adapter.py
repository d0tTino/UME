"""Redis-backed implementation of :class:`IGraphAdapter`."""
from __future__ import annotations

import importlib
import json
from typing import Any, Dict, List, Optional, Tuple, cast

from .graph_adapter import IGraphAdapter
from .processing import ProcessingError
from .graph_algorithms import GraphAlgorithmsMixin
from .audit import log_audit_entry
from .config import settings

_spec = importlib.util.find_spec("redis")
redis = importlib.import_module("redis") if _spec is not None else None


class RedisGraphAdapter(GraphAlgorithmsMixin, IGraphAdapter):
    """Simple graph adapter using Redis hashes and sets."""

    NODE_PREFIX = "node:"
    EDGE_PREFIX = "edge:"
    EDGE_SET_KEY = f"{EDGE_PREFIX}all"
    REDACTED_NODES_KEY = "redacted_nodes"
    REDACTED_EDGES_KEY = "redacted_edges"

    def __init__(self, url: str | None = None) -> None:
        if redis is None:
            raise ImportError("redis is required for RedisGraphAdapter")
        self._url = url or settings.UME_DB_PATH
        self._client = redis.from_url(self._url)

    # ---- Utility ------------------------------------------------------------
    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # pragma: no cover - connection closing best-effort
            pass

    def clear(self) -> None:
        for k in self._client.scan_iter(f"{self.NODE_PREFIX}*"):
            self._client.delete(k)
        for k in self._client.scan_iter(f"{self.EDGE_PREFIX}*"):
            self._client.delete(k)
        self._client.delete(self.REDACTED_NODES_KEY)
        self._client.delete(self.REDACTED_EDGES_KEY)

    # ---- Node methods -------------------------------------------------------
    def _node_key(self, node_id: str) -> str:
        return f"{self.NODE_PREFIX}{node_id}"

    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        if self.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' already exists.")
        self._client.set(self._node_key(node_id), json.dumps(attributes))

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        data = self.get_node(node_id)
        if data is None:
            raise ProcessingError(f"Node '{node_id}' not found for update.")
        data.update(attributes)
        self._client.set(self._node_key(node_id), json.dumps(data))

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if self._client.sismember(self.REDACTED_NODES_KEY, node_id):
            return None
        raw = self._client.get(self._node_key(node_id))
        if raw is None:
            return None
        return cast(Dict[str, Any], json.loads(raw))

    def node_exists(self, node_id: str) -> bool:
        return self._client.exists(self._node_key(node_id)) == 1 and not self._client.sismember(
            self.REDACTED_NODES_KEY,
            node_id,
        )

    def get_all_node_ids(self) -> List[str]:
        """Return all non-redacted node IDs."""
        return [
            node_id
            for k in self._client.scan_iter(f"{self.NODE_PREFIX}*")
            if not self._client.sismember(
                self.REDACTED_NODES_KEY,
                node_id := k.decode().split(":", 1)[1]
            )
        ]

    def dump(self) -> Dict[str, Any]:
        nodes: Dict[str, Any] = {}
        for k in self._client.scan_iter(f"{self.NODE_PREFIX}*"):
            node_id = k.decode().split(":", 1)[1]
            if self._client.sismember(self.REDACTED_NODES_KEY, node_id):
                continue
            raw = self._client.get(k)
            if raw is not None:
                nodes[node_id] = json.loads(raw)
        edges = self.get_all_edges()
        return {"nodes": nodes, "edges": edges}

    # ---- Edge methods -------------------------------------------------------
    def _edge_member(self, source: str, target: str, label: str) -> str:
        return f"{source}|{target}|{label}"

    def add_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        if not self.node_exists(source_node_id) or not self.node_exists(target_node_id):
            raise ProcessingError(
                f"Both source node '{source_node_id}' and target node '{target_node_id}' must exist to add an edge."
            )
        member = self._edge_member(source_node_id, target_node_id, label)
        if self._client.sismember(self.EDGE_SET_KEY, member):
            raise ProcessingError(
                f"Edge ({source_node_id}, {target_node_id}, {label}) already exists."
            )
        self._client.sadd(self.EDGE_SET_KEY, member)

    def get_all_edges(self) -> List[Tuple[str, str, str]]:
        result = []
        for b in self._client.smembers(self.EDGE_SET_KEY):
            member = b.decode()
            if self._client.sismember(self.REDACTED_EDGES_KEY, member):
                continue
            src, tgt, lbl = member.split("|", 2)
            if self._client.sismember(self.REDACTED_NODES_KEY, src) or self._client.sismember(
                self.REDACTED_NODES_KEY,
                tgt,
            ):
                continue
            result.append((src, tgt, lbl))
        return result

    def delete_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        member = self._edge_member(source_node_id, target_node_id, label)
        if self._client.srem(self.EDGE_SET_KEY, member) == 0:
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be deleted."
            )
        self._client.srem(self.REDACTED_EDGES_KEY, member)

    def find_connected_nodes(self, node_id: str, edge_label: Optional[str] = None) -> List[str]:
        if not self.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' not found.")
        connected: List[str] = []
        for b in self._client.smembers(self.EDGE_SET_KEY):
            member = b.decode()
            src, tgt, lbl = member.split("|", 2)
            if src != node_id:
                continue
            if edge_label is not None and lbl != edge_label:
                continue
            if self._client.sismember(self.REDACTED_EDGES_KEY, member):
                continue
            if self._client.sismember(self.REDACTED_NODES_KEY, tgt):
                continue
            connected.append(tgt)
        return connected

    # ---- Redaction ----------------------------------------------------------
    def redact_node(self, node_id: str) -> None:
        if not self.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' not found to redact.")
        self._client.sadd(self.REDACTED_NODES_KEY, node_id)
        log_audit_entry(settings.UME_AGENT_ID, f"redact_node {node_id}")

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        member = self._edge_member(source_node_id, target_node_id, label)
        if not self._client.sismember(self.EDGE_SET_KEY, member):
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be redacted."
            )
        self._client.sadd(self.REDACTED_EDGES_KEY, member)
        log_audit_entry(
            settings.UME_AGENT_ID,
            f"redact_edge {source_node_id} {target_node_id} {label}",
        )

