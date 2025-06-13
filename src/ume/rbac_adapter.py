"""Role-based wrapper around IGraphAdapter."""

from typing import Dict, Any, Optional, List

from .graph_adapter import IGraphAdapter


class AccessDeniedError(PermissionError):
    """Raised when a graph operation is not permitted for the current role."""


class RoleBasedGraphAdapter(IGraphAdapter):
    """Wraps another adapter and enforces basic role-based access control."""

    def __init__(self, adapter: IGraphAdapter, role: str):
        self._adapter = adapter
        self.role = role

    # Internal helpers -----------------------------------------------------
    def _check_user_profile_access(self, node_id: str) -> None:
        if node_id.startswith("UserProfile.") and self.role != "UserService":
            raise AccessDeniedError(
                "Only the 'UserService' role may modify UserProfile nodes"
            )

    def _require_analytics_role(self) -> None:
        if self.role != "AnalyticsAgent":
            raise AccessDeniedError(
                "Only the 'AnalyticsAgent' role may perform this operation"
            )

    # IGraphAdapter methods ------------------------------------------------
    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        self._check_user_profile_access(node_id)
        self._adapter.add_node(node_id, attributes)

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        self._check_user_profile_access(node_id)
        self._adapter.update_node(node_id, attributes)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self._adapter.get_node(node_id)

    def node_exists(self, node_id: str) -> bool:
        return self._adapter.node_exists(node_id)

    def dump(self) -> Dict[str, Any]:
        return self._adapter.dump()

    def clear(self) -> None:
        self._adapter.clear()

    def get_all_node_ids(self) -> list[str]:
        return self._adapter.get_all_node_ids()

    def find_connected_nodes(
        self, node_id: str, edge_label: Optional[str] = None
    ) -> list[str]:
        self._require_analytics_role()
        return self._adapter.find_connected_nodes(node_id, edge_label)

    def add_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        self._adapter.add_edge(source_node_id, target_node_id, label)

    def get_all_edges(self) -> list[tuple[str, str, str]]:
        return self._adapter.get_all_edges()

    def delete_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        self._adapter.delete_edge(source_node_id, target_node_id, label)

    def redact_node(self, node_id: str) -> None:
        self._require_analytics_role()
        self._adapter.redact_node(node_id)

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        self._require_analytics_role()
        self._adapter.redact_edge(source_node_id, target_node_id, label)

    def close(self) -> None:
        self._adapter.close()

    # ---- Traversal and pathfinding ---------------------------------

    def shortest_path(self, source_id: str, target_id: str) -> list[str]:
        self._require_analytics_role()
        return self._adapter.shortest_path(source_id, target_id)

    def traverse(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
    ) -> list[str]:
        self._require_analytics_role()
        return self._adapter.traverse(start_node_id, depth, edge_label)

    def extract_subgraph(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
        since_timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._require_analytics_role()
        return self._adapter.extract_subgraph(
            start_node_id, depth, edge_label, since_timestamp
        )

    def constrained_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int | None = None,
        edge_label: str | None = None,
        since_timestamp: int | None = None,
    ) -> List[str]:
        self._require_analytics_role()
        return self._adapter.constrained_path(
            source_id, target_id, max_depth, edge_label, since_timestamp
        )
