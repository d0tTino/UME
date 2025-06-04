import pytest
from ume import MockGraph, RoleBasedGraphAdapter, AccessDeniedError


def test_user_profile_edit_requires_user_service():
    graph = MockGraph()
    rbac = RoleBasedGraphAdapter(graph, role="AutoDev")
    with pytest.raises(AccessDeniedError):
        rbac.add_node("UserProfile.1", {})

    rbac_allowed = RoleBasedGraphAdapter(graph, role="UserService")
    rbac_allowed.add_node("UserProfile.1", {})
    assert graph.node_exists("UserProfile.1")


def test_find_connected_nodes_requires_analytics_agent():
    graph = MockGraph()
    graph.add_node("n1", {})
    rbac = RoleBasedGraphAdapter(graph, role="AutoDev")
    with pytest.raises(AccessDeniedError):
        rbac.find_connected_nodes("n1")

    analytics = RoleBasedGraphAdapter(graph, role="AnalyticsAgent")
    assert analytics.find_connected_nodes("n1") == []

