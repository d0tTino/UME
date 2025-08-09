import pytest
from ume import MockGraph, AccessDeniedError
from ume.permissions_adapter import PermissionsGraphAdapter


def build_graph() -> MockGraph:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("Document.d1", {"title": "doc1"})
    g.add_node("Document.d2", {"title": "doc2"})
    g._edges["Document.d1"].append(("User.u1", "HAS_PERMISSION", {"permission_level": "editor"}))
    return g


def test_update_requires_editor_permission() -> None:
    graph = build_graph()
    adapter = PermissionsGraphAdapter(graph, user_id="User.u1")
    adapter.update_node("Document.d1", {"title": "updated"})
    with pytest.raises(AccessDeniedError):
        adapter.update_node("Document.d2", {"title": "nope"})


def test_read_filters_invisible_nodes_and_edges() -> None:
    graph = build_graph()
    graph.add_edge("Document.d1", "Document.d2", "RELATED")
    adapter = PermissionsGraphAdapter(graph, user_id="User.u1")
    assert adapter.get_node("Document.d1") == {"title": "doc1"}
    assert adapter.get_node("Document.d2") is None
    assert adapter.get_all_node_ids() == ["Document.d1"]
    assert adapter.get_all_edges() == []


def test_group_viewer_allows_read_not_edit() -> None:
    g = MockGraph()
    g.add_node("Group.g1", {})
    g.add_node("Document.d1", {})
    g._edges["Document.d1"].append(("Group.g1", "HAS_PERMISSION", {"permission_level": "viewer"}))
    adapter = PermissionsGraphAdapter(g, group_id="Group.g1")
    assert adapter.get_node("Document.d1") == {}
    with pytest.raises(AccessDeniedError):
        adapter.update_node("Document.d1", {"foo": "bar"})


def test_get_nodes_by_user_and_group() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("Group.g1", {})
    g.add_node("Document.d1", {})
    g.add_node("Document.d2", {})
    g._edges["Document.d1"].append(("User.u1", "HAS_PERMISSION", {"permission_level": "editor"}))
    g._edges["Document.d2"].append(("Group.g1", "HAS_PERMISSION", {"permission_level": "viewer"}))
    adapter = PermissionsGraphAdapter(g, user_id="User.u1", group_id="Group.g1")
    assert set(adapter.get_nodes_by_user("User.u1")) == {"Document.d1"}
    assert set(adapter.get_nodes_shared_with("Group.g1")) == {"Document.d2"}


def test_add_edge_requires_editor_and_preserves_attrs() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("Document.d1", {})
    g.add_node("Document.d2", {})
    g._edges["Document.d1"].append(("User.u1", "HAS_PERMISSION", {"permission_level": "editor"}))
    adapter = PermissionsGraphAdapter(g, user_id="User.u1")
    with pytest.raises(AccessDeniedError):
        adapter.add_edge("Document.d1", "Document.d2", "RELATED", {"weight": 1})
    g._edges["Document.d2"].append(("User.u1", "HAS_PERMISSION", {"permission_level": "editor"}))
    adapter.add_edge("Document.d1", "Document.d2", "RELATED", {"weight": 1})
    assert adapter.get_all_edges() == [
        ("Document.d1", "Document.d2", "RELATED", {"weight": 1})
    ]


def test_find_connected_nodes_filters_by_permissions() -> None:
    g = build_graph()
    g.add_node("Document.d3", {})
    g.add_edge("Document.d1", "Document.d2", "RELATED")
    g.add_edge("Document.d1", "Document.d3", "RELATED")
    g._edges["Document.d3"].append(
        ("User.u1", "HAS_PERMISSION", {"permission_level": "viewer"})
    )
    adapter = PermissionsGraphAdapter(g, user_id="User.u1")
    assert adapter.find_connected_nodes("Document.d1") == ["Document.d3"]
    with pytest.raises(AccessDeniedError):
        adapter.find_connected_nodes("Document.d2")
