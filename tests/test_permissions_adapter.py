import pytest
from ume import MockGraph, AccessDeniedError
from ume.permissions_adapter import PermissionsGraphAdapter


def build_graph() -> MockGraph:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("Document.d1", {"title": "doc1"})
    g.add_node("Document.d2", {"title": "doc2"})
    g._edges["Document.d1"].append(("User.u1", "OWNED_BY", {"permission_level": "editor"}))
    return g


def test_get_nodes_by_user_handles_empty_and_rebuilt_indices() -> None:
    graph = build_graph()
    adapter = PermissionsGraphAdapter(graph, user_id="User.u1")

    # Initially only d1 is owned by the user.
    assert adapter.get_nodes_by_user("User.u1") == ["Document.d1"]

    # Add another ownership edge directly on the underlying graph and rebuild the index.
    graph._edges["Document.d2"].append(
        ("User.u1", "OWNED_BY", {"permission_level": "viewer"})
    )
    adapter.rebuild_index()
    assert set(adapter.get_nodes_by_user("User.u1")) == {"Document.d1", "Document.d2"}

    # Remove all edges and ensure rebuild clears the cached lookups.
    graph._edges["Document.d1"].clear()
    graph._edges["Document.d2"].clear()
    adapter.rebuild_index()
    assert adapter.get_nodes_by_user("User.u1") == []


def test_update_requires_editor_permission() -> None:
    graph = build_graph()
    graph._edges["Document.d2"].append(
        ("User.u1", "SHARED_WITH", {"permission_level": "viewer"})
    )
    adapter = PermissionsGraphAdapter(graph, user_id="User.u1")
    adapter.update_node("Document.d1", {"title": "updated"})
    assert adapter.get_node("Document.d2") == {"title": "doc2"}
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
    g._edges["Document.d1"].append(("Group.g1", "SHARED_WITH", {"permission_level": "viewer"}))
    adapter = PermissionsGraphAdapter(g, group_id="Group.g1")
    assert adapter.get_node("Document.d1") == {}
    with pytest.raises(AccessDeniedError):
        adapter.update_node("Document.d1", {"foo": "bar"})


def test_group_editor_allows_edit() -> None:
    g = MockGraph()
    g.add_node("Group.g1", {})
    g.add_node("Document.d1", {"title": "doc1"})
    g._edges["Document.d1"].append(("Group.g1", "SHARED_WITH", {"permission_level": "editor"}))
    adapter = PermissionsGraphAdapter(g, group_id="Group.g1")
    adapter.update_node("Document.d1", {"title": "updated"})
    assert adapter.get_node("Document.d1") == {"title": "updated"}


def test_get_nodes_by_user_and_group() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("Group.g1", {})
    g.add_node("Document.d1", {})
    g.add_node("Document.d2", {})
    g._edges["Document.d1"].append(("User.u1", "OWNED_BY", {"permission_level": "editor"}))
    g._edges["Document.d2"].append(("Group.g1", "SHARED_WITH", {"permission_level": "viewer"}))
    adapter = PermissionsGraphAdapter(g, user_id="User.u1", group_id="Group.g1")
    assert set(adapter.get_nodes_by_user("User.u1")) == {"Document.d1"}
    assert set(adapter.get_nodes_shared_with("Group.g1")) == {"Document.d2"}


def test_get_nodes_by_user_various_permissions() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("Group.g1", {})
    g.add_node("Group.g2", {})

    # Nodes owned by the user with different permission levels
    g.add_node("Document.u_viewer", {})
    g._edges["Document.u_viewer"].append(
        ("User.u1", "OWNED_BY", {"permission_level": "viewer"})
    )
    g.add_node("Document.u_editor", {})
    g._edges["Document.u_editor"].append(
        ("User.u1", "OWNED_BY", {"permission_level": "editor"})
    )

    # Node shared with a group and owned by the user
    g.add_node("Document.mixed_user_group1", {})
    g._edges["Document.mixed_user_group1"].append(
        ("User.u1", "OWNED_BY", {"permission_level": "viewer"})
    )
    g._edges["Document.mixed_user_group1"].append(
        ("Group.g1", "SHARED_WITH", {"permission_level": "editor"})
    )

    # Nodes only shared with groups should not appear
    g.add_node("Document.g1_viewer", {})
    g._edges["Document.g1_viewer"].append(
        ("Group.g1", "SHARED_WITH", {"permission_level": "viewer"})
    )
    g.add_node("Document.g2_editor", {})
    g._edges["Document.g2_editor"].append(
        ("Group.g2", "SHARED_WITH", {"permission_level": "editor"})
    )

    adapter = PermissionsGraphAdapter(g, user_id="User.u1", group_id="Group.g1")
    result = set(adapter.get_nodes_by_user("User.u1"))
    assert result == {
        "Document.u_viewer",
        "Document.u_editor",
        "Document.mixed_user_group1",
    }


def test_get_nodes_shared_with_multiple_groups_and_mixed_permissions() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("Group.g1", {})
    g.add_node("Group.g2", {})

    # Nodes shared with group1
    g.add_node("Document.g1_viewer", {})
    g._edges["Document.g1_viewer"].append(
        ("Group.g1", "SHARED_WITH", {"permission_level": "viewer"})
    )
    g.add_node("Document.g1_editor", {})
    g._edges["Document.g1_editor"].append(
        ("Group.g1", "SHARED_WITH", {"permission_level": "editor"})
    )

    # Nodes shared with group2
    g.add_node("Document.g2_viewer", {})
    g._edges["Document.g2_viewer"].append(
        ("Group.g2", "SHARED_WITH", {"permission_level": "viewer"})
    )
    g.add_node("Document.g2_editor", {})
    g._edges["Document.g2_editor"].append(
        ("Group.g2", "SHARED_WITH", {"permission_level": "editor"})
    )

    # Mixed cases
    g.add_node("Document.mixed_user_group1", {})
    g._edges["Document.mixed_user_group1"].append(
        ("User.u1", "OWNED_BY", {"permission_level": "viewer"})
    )
    g._edges["Document.mixed_user_group1"].append(
        ("Group.g1", "SHARED_WITH", {"permission_level": "editor"})
    )
    g.add_node("Document.mixed_groups", {})
    g._edges["Document.mixed_groups"].append(
        ("Group.g1", "SHARED_WITH", {"permission_level": "viewer"})
    )
    g._edges["Document.mixed_groups"].append(
        ("Group.g2", "SHARED_WITH", {"permission_level": "editor"})
    )

    adapter_g1 = PermissionsGraphAdapter(g, group_id="Group.g1")
    assert set(adapter_g1.get_nodes_shared_with("Group.g1")) == {
        "Document.g1_viewer",
        "Document.g1_editor",
        "Document.mixed_user_group1",
        "Document.mixed_groups",
    }

    adapter_g2 = PermissionsGraphAdapter(g, group_id="Group.g2")
    assert set(adapter_g2.get_nodes_shared_with("Group.g2")) == {
        "Document.g2_viewer",
        "Document.g2_editor",
        "Document.mixed_groups",
    }

def test_add_edge_requires_editor_and_preserves_attrs() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("Document.d1", {})
    g.add_node("Document.d2", {})
    g._edges["Document.d1"].append(("User.u1", "OWNED_BY", {"permission_level": "editor"}))
    adapter = PermissionsGraphAdapter(g, user_id="User.u1")
    with pytest.raises(AccessDeniedError):
        adapter.add_edge("Document.d1", "Document.d2", "TAGGED_AS", {"weight": 1})
    g._edges["Document.d2"].append(("User.u1", "OWNED_BY", {"permission_level": "editor"}))
    adapter.rebuild_index()
    adapter.add_edge("Document.d1", "Document.d2", "TAGGED_AS", {"weight": 1})
    assert adapter.get_all_edges() == [
        (
            "Document.d1",
            "Document.d2",
            "TAGGED_AS",
            {"weight": 1, "schema_version": "3.0.0"},
        )
    ]


def test_add_permission_edge_requires_permission_level() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("User.u2", {})
    g.add_node("Document.d1", {})
    g._edges["Document.d1"].append(("User.u1", "OWNED_BY", {"permission_level": "editor"}))
    adapter = PermissionsGraphAdapter(g, user_id="User.u1")

    with pytest.raises(AccessDeniedError) as excinfo:
        adapter.add_edge("Document.d1", "User.u2", "SHARED_WITH")
    assert "permission_level is required" in str(excinfo.value)
    assert not any(
        tgt == "User.u2" and lbl == "SHARED_WITH"
        for _, tgt, lbl, _ in g.get_all_edges()
    )

    with pytest.raises(AccessDeniedError):
        adapter.add_edge(
            "Document.d1",
            "User.u2",
            "SHARED_WITH",
            {"permission_level": ""},
        )


def test_find_connected_nodes_filters_by_permissions() -> None:
    g = build_graph()
    g.add_node("Document.d3", {})
    g.add_edge("Document.d1", "Document.d2", "RELATED")
    g.add_edge("Document.d1", "Document.d3", "RELATED")
    g._edges["Document.d3"].append(
        ("User.u1", "SHARED_WITH", {"permission_level": "viewer"})
    )
    adapter = PermissionsGraphAdapter(g, user_id="User.u1")
    assert adapter.find_connected_nodes("Document.d1") == ["Document.d3"]
    with pytest.raises(AccessDeniedError):
        adapter.find_connected_nodes("Document.d2")


def test_add_permission_edge_without_target_editor() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("User.u2", {})
    g.add_node("Document.d1", {})
    g._edges["Document.d1"].append(("User.u1", "OWNED_BY", {"permission_level": "editor"}))
    adapter = PermissionsGraphAdapter(g, user_id="User.u1")
    adapter.add_edge(
        "Document.d1",
        "User.u2",
        "SHARED_WITH",
        {"permission_level": "viewer"},
    )
    adapter_u2 = PermissionsGraphAdapter(g, user_id="User.u2")
    assert adapter_u2.get_node("Document.d1") == {}


def test_owned_by_edge_sets_schema_version_and_allows_edit() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("User.u2", {})
    g.add_node("Document.d1", {"title": "doc1"})
    g._edges["Document.d1"].append(
        (
            "User.u1",
            "OWNED_BY",
            {"permission_level": "editor", "schema_version": "3.0.0"},
        )
    )
    adapter = PermissionsGraphAdapter(g, user_id="User.u1")
    adapter.add_edge(
        "Document.d1",
        "User.u2",
        "OWNED_BY",
        {"permission_level": "editor"},
    )
    edge_attrs = next(
        attrs
        for s, t, lbl, attrs in g.get_all_edges()
        if s == "Document.d1" and t == "User.u2" and lbl == "OWNED_BY"
    )
    assert edge_attrs["schema_version"] == "3.0.0"
    adapter_u2 = PermissionsGraphAdapter(g, user_id="User.u2")
    adapter_u2.update_node("Document.d1", {"title": "updated"})
    assert g.get_node("Document.d1") == {"title": "updated"}


def test_shared_with_edge_sets_schema_version_and_allows_view_only() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("User.u2", {})
    g.add_node("Document.d1", {"title": "doc1"})
    g._edges["Document.d1"].append(
        (
            "User.u1",
            "OWNED_BY",
            {"permission_level": "editor", "schema_version": "3.0.0"},
        )
    )
    adapter = PermissionsGraphAdapter(g, user_id="User.u1")
    adapter.add_edge(
        "Document.d1",
        "User.u2",
        "SHARED_WITH",
        {"permission_level": "viewer"},
    )
    edge_attrs = next(
        attrs
        for s, t, lbl, attrs in g.get_all_edges()
        if s == "Document.d1" and t == "User.u2" and lbl == "SHARED_WITH"
    )
    assert edge_attrs["schema_version"] == "3.0.0"
    adapter_u2 = PermissionsGraphAdapter(g, user_id="User.u2")
    assert adapter_u2.get_node("Document.d1") == {"title": "doc1"}
    with pytest.raises(AccessDeniedError):
        adapter_u2.update_node("Document.d1", {"title": "nope"})


def test_add_edge_rejects_invalid_permission_level() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("User.u2", {})
    g.add_node("Document.d1", {"title": "doc1"})
    g._edges["Document.d1"].append(
        ("User.u1", "OWNED_BY", {"permission_level": "editor"})
    )
    adapter = PermissionsGraphAdapter(g, user_id="User.u1")
    with pytest.raises(AccessDeniedError):
        adapter.add_edge(
            "Document.d1",
            "User.u2",
            "SHARED_WITH",
            {"permission_level": "admin"},
        )


def test_add_edge_invalid_permission_level_on_non_permission_edge() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("Document.d1", {})
    g.add_node("Document.d2", {})
    g._edges["Document.d1"].append(("User.u1", "OWNED_BY", {"permission_level": "editor"}))
    g._edges["Document.d2"].append(("User.u1", "OWNED_BY", {"permission_level": "editor"}))
    adapter = PermissionsGraphAdapter(g, user_id="User.u1")
    with pytest.raises(AccessDeniedError):
        adapter.add_edge(
            "Document.d1",
            "Document.d2",
            "TAGGED_AS",
            {"permission_level": "owner"},
        )


def test_delete_shared_with_and_invites_without_target_editor() -> None:
    g = MockGraph()
    g.add_node("User.u1", {})
    g.add_node("User.u2", {})
    g.add_node("Group.g1", {})
    g.add_node("Document.d1", {})
    g._edges["Document.d1"].append(
        ("User.u1", "OWNED_BY", {"permission_level": "editor"})
    )
    g._edges["Document.d1"].append(
        ("Group.g1", "SHARED_WITH", {"permission_level": "viewer"})
    )
    g._edges["Document.d1"].append(("User.u2", "INVITES", {}))

    adapter = PermissionsGraphAdapter(g, user_id="User.u1")

    adapter.delete_edge("Document.d1", "Group.g1", "SHARED_WITH")
    assert not any(
        s == "Document.d1" and t == "Group.g1" and lbl == "SHARED_WITH"
        for s, t, lbl, _ in g.get_all_edges()
    )

    adapter.delete_edge("Document.d1", "User.u2", "INVITES")
    assert not any(
        s == "Document.d1" and t == "User.u2" and lbl == "INVITES"
        for s, t, lbl, _ in g.get_all_edges()
    )
