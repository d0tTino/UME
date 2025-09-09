from datetime import datetime

from ume import MockGraph
from ume.models import create_calendar_event, create_decision_analysis
from ume.permissions_adapter import PermissionsGraphAdapter


def test_calendar_event_schema_version() -> None:
    start = datetime.utcnow()
    event = create_calendar_event("Meeting", start)
    assert event.schema_version == "3.0.0"


def test_decision_analysis_schema_version() -> None:
    analysis = create_decision_analysis("should we proceed?")
    assert analysis.schema_version == "3.0.0"


def test_permission_edge_schema_version() -> None:
    graph = MockGraph()
    graph.add_node("User.u1", {})
    graph.add_node("User.u2", {})
    graph.add_node("Document.d1", {})
    graph._edges["Document.d1"].append(
        ("User.u1", "OWNED_BY", {"permission_level": "editor", "schema_version": "3.0.0"})
    )
    adapter = PermissionsGraphAdapter(graph, user_id="User.u1")
    adapter.add_edge(
        "Document.d1",
        "User.u2",
        "SHARED_WITH",
        {"permission_level": "viewer"},
    )
    edge_attrs = next(
        attrs
        for s, t, lbl, attrs in graph.get_all_edges()
        if s == "Document.d1" and t == "User.u2" and lbl == "SHARED_WITH"
    )
    assert edge_attrs["schema_version"] == "3.0.0"
