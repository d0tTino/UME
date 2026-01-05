"""Permission-based wrapper around IGraphAdapter."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from typing import Any, DefaultDict, Dict, List, Optional

from .graph_adapter import IGraphAdapter
from .rbac_adapter import AccessDeniedError
from .graph_schema import DEFAULT_SCHEMA


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
        self._edges_by_source: DefaultDict[str, List[tuple[str, str, Any]]] = defaultdict(list)
        self._edges_by_target: DefaultDict[str, List[tuple[str, str, Any]]] = defaultdict(list)
        self._bootstrap_owner_nodes: set[str] = set()
        self.rebuild_index()

    # ------------------------------------------------------------------
    # Internal helpers
    def _subjects(self) -> list[str]:
        return [s for s in [self.user_id, self.group_id] if s]

    def rebuild_index(self) -> None:
        """Rebuild the edge lookup tables from the underlying adapter."""
        self._edges_by_source.clear()
        self._edges_by_target.clear()
        for src, tgt, lbl, attrs in self._adapter.get_all_edges():
            self._edges_by_source[src].append((tgt, lbl, attrs))
            self._edges_by_target[tgt].append((src, lbl, attrs))

    def _has_permission_edge(self, node_id: str, subject: str, perm: str) -> bool:
        for tgt, lbl, attrs in self._edges_by_source.get(node_id, []):
            if tgt != subject or lbl not in {"OWNED_BY", "SHARED_WITH"}:
                continue
            perm_level = attrs.get("permission_level") if isinstance(attrs, dict) else attrs
            if not self._is_valid_permission_level(lbl, perm_level):
                continue
            if perm_level == perm:
                return True
            if perm == "viewer" and perm_level == "editor":
                return True
        return False

    def _is_valid_permission_level(self, label: str, perm_level: Any) -> bool:
        if not isinstance(perm_level, str) or not perm_level:
            return False
        edge_def = DEFAULT_SCHEMA.edge_labels.get(label)
        if edge_def is None:
            return False
        accepted = set(edge_def.permission_level_values)
        if not accepted and edge_def.permission_level is not None:
            accepted.add(edge_def.permission_level)
        return bool(accepted) and perm_level in accepted

    def _has_permission(self, node_id: str, perm: str) -> bool:
        for subject in self._subjects():
            if self._has_permission_edge(node_id, subject, perm):
                return True
            if perm == "viewer" and self._has_permission_edge(node_id, subject, "editor"):
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
        self.rebuild_index()

    def get_all_node_ids(self) -> List[str]:
        return self._filter_visible(self._adapter.get_all_node_ids())

    def _get_nodes_for_subject(self, subject_id: str, labels: List[str]) -> List[str]:
        nodes: set[str] = set()
        for src, lbl, attrs in self._edges_by_target.get(subject_id, []):
            if lbl not in labels:
                continue
            perm_level = attrs.get("permission_level") if isinstance(attrs, dict) else attrs
            if self._is_valid_permission_level(lbl, perm_level):
                nodes.add(src)
        return list(nodes)

    def get_nodes_by_user(self, user_id: str) -> List[str]:
        return self._filter_visible(
            self._get_nodes_for_subject(user_id, ["OWNED_BY", "SHARED_WITH"])
        )

    def get_nodes_shared_with(self, group_id: str) -> List[str]:
        return self._filter_visible(
            self._get_nodes_for_subject(group_id, ["SHARED_WITH"])
        )

    def find_connected_nodes(
        self, node_id: str, edge_label: Optional[str] = None
    ) -> List[str]:
        if not self._has_permission(node_id, "viewer"):
            raise AccessDeniedError(f"Viewer permission required for '{node_id}'")
        connected = self._adapter.find_connected_nodes(node_id, edge_label)
        return self._filter_visible(connected)

    @contextmanager
    def bootstrap_owner(self, node_id: str):
        """Temporarily allow setting the initial OWNED_BY edge for a node."""

        self._bootstrap_owner_nodes.add(node_id)
        try:
            yield
        finally:
            self._bootstrap_owner_nodes.discard(node_id)

    def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, Any] | None = None,
        schema_version: str | None = None,
    ) -> None:
        is_bootstrap_owner = (
            label == "OWNED_BY" and source_node_id in self._bootstrap_owner_nodes
        )
        if not is_bootstrap_owner:
            if label == "OWNED_BY" and not self._has_permission(
                source_node_id, "editor"
            ):
                raise AccessDeniedError(
                    "OWNED_BY edges must be bootstrapped before an editor exists"
                )
            self._require_editor(source_node_id)
        if label not in {"OWNED_BY", "SHARED_WITH", "INVITES"}:
            if not is_bootstrap_owner:
                self._require_editor(target_node_id)
        edge_def = DEFAULT_SCHEMA.edge_labels.get(label)
        version = edge_def.version if edge_def else schema_version
        if attrs is not None and not isinstance(attrs, dict):
            raise AccessDeniedError("Edge attributes must be a mapping when provided")
        attrs = dict(attrs or {})
        perm_level = attrs.get("permission_level")
        if label in {"OWNED_BY", "SHARED_WITH"}:
            if perm_level is None or (isinstance(perm_level, str) and not perm_level):
                raise AccessDeniedError(
                    "permission_level is required for OWNED_BY/SHARED_WITH edges"
                )
        if perm_level is not None:
            if not isinstance(perm_level, str) or not perm_level:
                raise AccessDeniedError(
                    "permission_level must be a non-empty string when provided"
                )
            if edge_def is None:
                raise AccessDeniedError("permission_level not allowed for unknown edge")
            accepted = set(edge_def.permission_level_values)
            if not accepted and edge_def.permission_level is not None:
                accepted.add(edge_def.permission_level)
            if not accepted or perm_level not in accepted:
                raise AccessDeniedError(
                    f"Invalid permission_level '{perm_level}'"
                )
        attrs.pop("schema_version", None)
        self._adapter.add_edge(
            source_node_id,
            target_node_id,
            label,
            attrs,
            schema_version=version,
        )
        self.rebuild_index()

    def get_all_edges(self) -> List[tuple[str, str, str, Dict[str, Any]]]:
        edges = self._adapter.get_all_edges()
        return [
            (s, t, lbl, attrs)
            for s, t, lbl, attrs in edges
            if self._has_permission(s, "viewer") and self._has_permission(t, "viewer")

        ]

    def delete_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, Any] | None = None,
    ) -> None:
        self._require_editor(source_node_id)
        if label not in {"OWNED_BY", "SHARED_WITH", "INVITES"}:
            self._require_editor(target_node_id)
        self._adapter.delete_edge(source_node_id, target_node_id, label, attrs)
        self.rebuild_index()

    def redact_node(self, node_id: str) -> None:
        self._require_editor(node_id)
        self._adapter.redact_node(node_id)
        self.rebuild_index()

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        self._require_editor(source_node_id)
        self._require_editor(target_node_id)
        self._adapter.redact_edge(source_node_id, target_node_id, label)
        self.rebuild_index()

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
            edge
            for edge in subgraph.get("edges", [])
            if self._has_permission(edge[0], "viewer")
            and self._has_permission(edge[1], "viewer")
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
