"""ArangoDB-backed implementation of :class:`IGraphAdapter`."""
from __future__ import annotations

import importlib
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Iterable, cast

from .graph_adapter import IGraphAdapter
from .processing import ProcessingError
from .graph_algorithms import GraphAlgorithmsMixin
from .audit import log_audit_entry
from .config import settings
from .replay_mixin import ReplayMixin

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from arango.database import StandardDatabase
    from arango.client import ArangoClient
else:  # pragma: no cover - optional dependency
    _spec = importlib.util.find_spec("arango")
    if _spec is not None:
        from arango.client import ArangoClient  # type: ignore[attr-defined]
        from arango.database import StandardDatabase
    else:  # pragma: no cover - when dependency missing
        ArangoClient = None  # type: ignore
        StandardDatabase = None  # type: ignore


class ArangoGraph(ReplayMixin, GraphAlgorithmsMixin, IGraphAdapter):
    """Graph adapter using the ``python-arango`` driver."""

    def __init__(
        self,
        url: str,
        user: str,
        password: str,
        *,
        db_name: str = "ume",
        db: Optional["StandardDatabase"] = None,
    ) -> None:
        if ArangoClient is None:
            raise ImportError("python-arango is required for ArangoGraph")
        if db is None:
            client = ArangoClient(hosts=url)
            sys_db = client.db("_system", username=user, password=password)
            if not sys_db.has_database(db_name):
                sys_db.create_database(db_name)
            db = client.db(db_name, username=user, password=password)
        assert db is not None
        self._db = db
        if not self._db.has_collection("nodes"):
            self._db.create_collection("nodes")
        if not self._db.has_collection("edges"):
            self._db.create_collection("edges")
        self._nodes = self._db.collection("nodes")
        self._edges = self._db.collection("edges")

    # ---- Utility ------------------------------------------------------------
    def close(self) -> None:  # pragma: no cover - nothing to close
        pass

    def clear(self) -> None:
        self._nodes.truncate()
        self._edges.truncate()

    # ---- Node methods -------------------------------------------------------
    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        if self._nodes.has(node_id):
            raise ProcessingError(f"Node '{node_id}' already exists.")
        doc = {
            "_key": node_id,
            **attributes,
            "redacted": False,
            "created_at": int(time.time()),
        }
        self._nodes.insert(doc)

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        doc = cast(Optional[Dict[str, Any]], self._nodes.get(node_id))
        if doc is None or doc.get("redacted"):
            raise ProcessingError(f"Node '{node_id}' not found for update.")
        doc.update(attributes)
        self._nodes.update(doc)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        doc = cast(Optional[Dict[str, Any]], self._nodes.get(node_id))
        if doc is None or doc.get("redacted"):
            return None
        result = doc.copy()
        result.pop("_key", None)
        result.pop("_id", None)
        result.pop("_rev", None)
        return result

    def node_exists(self, node_id: str) -> bool:
        doc = cast(Optional[Dict[str, Any]], self._nodes.get(node_id))
        return doc is not None and not doc.get("redacted", False)

    def get_all_node_ids(self) -> List[str]:
        all_docs = list(cast(Iterable[Dict[str, Any]], self._nodes.all()))
        return [d["_key"] for d in all_docs if not d.get("redacted", False)]

    def dump(self) -> Dict[str, Any]:
        nodes: Dict[str, Any] = {}
        for d in cast(Iterable[Dict[str, Any]], self._nodes.all()):
            if d.get("redacted"):
                continue
            nid = d.get("_key")
            if nid is None:
                continue
            item = d.copy()
            item.pop("_key", None)
            item.pop("_id", None)
            item.pop("_rev", None)
            nodes[nid] = item
        edges = self.get_all_edges()
        return {"nodes": nodes, "edges": edges}

    # ---- Edge helpers -------------------------------------------------------
    def _edge_key(self, source: str, target: str, label: str) -> str:
        return f"{source}|{target}|{label}"

    # ---- Edge methods -------------------------------------------------------
    def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, Any] | None = None,
    ) -> None:
        if not self.node_exists(source_node_id) or not self.node_exists(target_node_id):
            raise ProcessingError(
                f"Both source node '{source_node_id}' and target node '{target_node_id}' must exist to add an edge."
            )
        key = self._edge_key(source_node_id, target_node_id, label)
        if self._edges.has(key):
            raise ProcessingError(f"Edge ({source_node_id}, {target_node_id}, {label}) already exists.")
        self._edges.insert({
            "_key": key,
            "source": source_node_id,
            "target": target_node_id,
            "label": label,
            "redacted": False,
            "created_at": int(time.time()),
        })

    def get_all_edges(self) -> List[Tuple[str, str, str, Dict[str, Any]]]:
        result: List[Tuple[str, str, str, Dict[str, Any]]] = []
        for e in cast(Iterable[Dict[str, Any]], self._edges.all()):
            if e.get("redacted"):
                continue
            if not self.node_exists(e["source"]) or not self.node_exists(e["target"]):
                continue
            result.append((e["source"], e["target"], e["label"], {}))
        return result

    def delete_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, Any] | None = None,
    ) -> None:
        key = self._edge_key(source_node_id, target_node_id, label)
        if not self._edges.has(key):
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be deleted."
            )
        self._edges.delete(key)

    def find_connected_nodes(self, node_id: str, edge_label: Optional[str] = None) -> List[str]:
        if not self.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' not found.")
        connected: List[str] = []
        for e in cast(Iterable[Dict[str, Any]], self._edges.find({"source": node_id})):
            if edge_label is not None and e["label"] != edge_label:
                continue
            if e.get("redacted"):
                continue
            if self.node_exists(e["target"]):
                connected.append(e["target"])
        return connected

    # ---- Redaction ----------------------------------------------------------
    def redact_node(self, node_id: str) -> None:
        doc = cast(Optional[Dict[str, Any]], self._nodes.get(node_id))
        if doc is None:
            raise ProcessingError(f"Node '{node_id}' not found to redact.")
        doc["redacted"] = True
        self._nodes.update(doc)
        log_audit_entry(settings.UME_AGENT_ID, f"redact_node {node_id}")

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        key = self._edge_key(source_node_id, target_node_id, label)
        doc = cast(Optional[Dict[str, Any]], self._edges.get(key))
        if doc is None:
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be redacted."
            )
        doc["redacted"] = True
        self._edges.update(doc)
        log_audit_entry(settings.UME_AGENT_ID, f"redact_edge {source_node_id} {target_node_id} {label}")

    # ---- Misc utilities -----------------------------------------------------
    def purge_old_records(self, max_age_seconds: int) -> None:
        cutoff = int(time.time()) - max_age_seconds - 1
        for doc in list(cast(Iterable[Dict[str, Any]], self._edges.find({}))):
            if doc.get("created_at", 0) < cutoff:
                self._edges.delete(doc)
        for doc in list(cast(Iterable[Dict[str, Any]], self._nodes.find({}))):
            if doc.get("created_at", 0) < cutoff:
                self._nodes.delete(doc)

