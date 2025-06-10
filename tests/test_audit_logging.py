import time
import os
import pytest


def test_audit_entry_on_policy_violation(tmp_path, monkeypatch):
    monkeypatch.setenv("UME_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UME_AGENT_ID", "tester")
    import importlib
    import ume

    importlib.reload(ume.config)
    importlib.reload(ume.audit)
    importlib.reload(ume.plugins.alignment)
    importlib.reload(ume.plugins.alignment.sample_policy)
    importlib.reload(ume.persistent_graph)
    importlib.reload(ume)

    from ume import (
        Event,
        EventType,
        apply_event_to_graph,
        MockGraph,
        get_audit_entries,
        PolicyViolationError,
    )

    open(os.environ["UME_AUDIT_LOG_PATH"], "w").close()
    start = len(get_audit_entries())

    graph = MockGraph()
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"node_id": "forbidden", "attributes": {"type": "UserMemory"}},
    )
    with pytest.raises(PolicyViolationError):
        apply_event_to_graph(event, graph)
    entries = get_audit_entries()
    assert len(entries) == start + 1
    assert entries[-1]["user_id"] == "tester"
    assert "forbidden" in entries[-1]["reason"]


def test_audit_entry_on_redactions(tmp_path, monkeypatch):
    monkeypatch.setenv("UME_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UME_AGENT_ID", "redactor")
    import importlib
    import ume

    importlib.reload(ume.config)
    importlib.reload(ume.audit)
    importlib.reload(ume.plugins.alignment)
    importlib.reload(ume.plugins.alignment.sample_policy)
    importlib.reload(ume.persistent_graph)
    importlib.reload(ume)

    from ume import PersistentGraph, get_audit_entries

    open(os.environ["UME_AUDIT_LOG_PATH"], "w").close()
    start = len(get_audit_entries())

    g = PersistentGraph(":memory:")
    g.add_node("n1", {})
    g.add_node("n2", {})
    g.add_edge("n1", "n2", "L")

    g.redact_node("n1")
    g.redact_edge("n1", "n2", "L")

    entries = get_audit_entries()
    assert len(entries) == start + 2
    assert entries[-2]["reason"].startswith("redact_node")
    assert entries[-1]["reason"].startswith("redact_edge")
    assert all(e["user_id"] == "redactor" for e in entries[-2:])


def test_s3_path_without_boto3(monkeypatch):
    """Using an S3 path without boto3 should raise ImportError."""
    import sys
    import importlib

    monkeypatch.setitem(sys.modules, "boto3", None)
    import ume.audit as audit

    importlib.reload(audit)

    with pytest.raises(ImportError):
        audit._read_lines("s3://bucket/key")
    with pytest.raises(ImportError):
        audit._write_lines("s3://bucket/key", ["x"])
