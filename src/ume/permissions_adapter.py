"""Permission-based wrapper around IGraphAdapter."""

from __future__ import annotations

from typing import Dict, Any, Optional, List

from .graph_adapter import IGraphAdapter
from .rbac_adapter import AccessDeniedError


class PermissionsGraphAdapter(IGraphAdapter):
    """Enforce viewer/editor permissions based on graph edges."""

    def __init__(
        self,
        adapter: IGraphAdapter,
        *,
        user_id: str | None = None,
        group_id: str | None = None,
    ) -> None:
        self._adapter = adapter
        self.user_id = user_id
        self.group_id = group_id

    # ------------------------------------------------------------------
    # Internal helpers
    def _subjects(self) -> list[str]:
        return [s for s in [self.user_id, self.group_id] if s]

    def _has_permission_edge(self, subject: str, node_id: str, label: str) -> bool:
        for src, tgt, lbl, _ in self._adapter.get_all_edges():
            if src == subject and tgt == node_id and lbl == label:
                return True
        return False

    def _has_permission(self, node_id: str, perm: str) -> bool:
        for subject in self._subjects():
            if self._has_permission_edge(subject, node_id, perm):
                return True
            if perm == "viewer" and self._has_permission_edge(subject, node_id, "editor"):
                return True
        return False

    def _require_editor(self, node_id: str) -> None:
        if not self._has_permission(node_id, "editor"):
            raise AccessDeniedError(f"Editor permission required for '{node_id}'")

    def _filter_visible(self, node_ids: List[str]) -> List[str]:
        return [nid for nid in node_ids if self._has_permission(nid, "viewer")]

    # ------------------------------------------------------------------
    # IGraphAdapter methods
    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        self._adapter.add_node(node_id, attributes)

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        self._require_editor(node_id)
        self._adapter.update_node(node_id, attributes)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if not self._has_permission(node_id, "viewer"):
            return None
        return self._adapter.get_node(node_id)

    def node_exists(self, node_id: str) -> bool:
        return self._has_permission(node_id, "viewer") and self._adapter.node_exists(node_id)

    def dump(self) -> Dict[str, Any]:
        data = self._adapter.dump()
        data["nodes"] = {
            nid: attrs
            for nid, attrs in data.get("nodes", {}).items()
            if self._has_permission(nid, "viewer")
        }
        data["edges"] = [
            (s, t, lbl, attrs)
            for s, t, lbl, attrs in data.get("edges", [])
            if self._has_permission(s, "viewer") and self._has_permission(t, "viewer")
        ]
        return data

    def clear(self) -> None:
        self._adapter.clear()

    def get_all_node_ids(self) -> List[str]:
        return self._filter_visible(self._adapter.get_all_node_ids())

    def find_connected_nodes(
        self, node_id: str, edge_label: Optional[str] = None
    ) -> List[str]:
        if not self._has_permission(node_id, "viewer"):
            raise AccessDeniedError(f"Viewer permission required for '{node_id}'")
        connected = self._adapter.find_connected_nodes(node_id, edge_label)
        return self._filter_visible(connected)

    def add_edge(
        self, source_node_id: str, target_node_id: str, label: str, **attrs: Any
    ) -> None:
        self._require_editor(source_node_id)
        self._require_editor(target_node_id)
        self._adapter.add_edge(source_node_id, target_node_id, label, **attrs)

    def get_all_edges(self) -> List[tuple[str, str, str, Dict[str, Any]]]:
        edges = self._adapter.get_all_edges()
        return [
            (s, t, lbl, attrs)
            for s, t, lbl, attrs in edges
            if self._has_permission(s, "viewer") and self._has_permission(t, "viewer")
        ]

    def delete_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        self._require_editor(source_node_id)
        self._require_editor(target_node_id)
        self._adapter.delete_edge(source_node_id, target_node_id, label)

    def redact_node(self, node_id: str) -> None:
        self._require_editor(node_id)
        self._adapter.redact_node(node_id)

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        self._require_editor(source_node_id)
        self._require_editor(target_node_id)
        self._adapter.redact_edge(source_node_id, target_node_id, label)

    def close(self) -> None:
        self._adapter.close()

    # ---- Traversal and pathfinding ---------------------------------
    def shortest_path(self, source_id: str, target_id: str) -> List[str]:
        if not (
            self._has_permission(source_id, "viewer")
            and self._has_permission(target_id, "viewer")
        ):
            return []
        path = self._adapter.shortest_path(source_id, target_id)
        return self._filter_visible(path)

    def traverse(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
    ) -> List[str]:
        if not self._has_permission(start_node_id, "viewer"):
            raise AccessDeniedError(
                f"Viewer permission required for '{start_node_id}'"
            )
        nodes = self._adapter.traverse(start_node_id, depth, edge_label)
        return self._filter_visible(nodes)

    def extract_subgraph(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
        since_timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not self._has_permission(start_node_id, "viewer"):
            raise AccessDeniedError(
                f"Viewer permission required for '{start_node_id}'"
            )
        subgraph = self._adapter.extract_subgraph(
            start_node_id, depth, edge_label, since_timestamp
        )
        subgraph["nodes"] = {
            nid: attrs
            for nid, attrs in subgraph.get("nodes", {}).items()
            if self._has_permission(nid, "viewer")
        }
        subgraph["edges"] = [
            (s, t, lbl)
            for s, t, lbl in subgraph.get("edges", [])
            if self._has_permission(s, "viewer")
            and self._has_permission(t, "viewer")
        ]
        return subgraph

    def constrained_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int | None = None,
        edge_label: str | None = None,
        since_timestamp: int | None = None,
    ) -> List[str]:
        if not (
            self._has_permission(source_id, "viewer")
            and self._has_permission(target_id, "viewer")
        ):
            return []
        path = self._adapter.constrained_path(
            source_id, target_id, max_depth, edge_label, since_timestamp
        )
        return self._filter_visible(path)
