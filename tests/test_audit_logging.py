import time
import os

os.environ.setdefault("UME_AUDIT_SIGNING_KEY", "test-key")
import pytest

# Skip heavy optional dependencies if they aren't installed
for _mod in (
    "httpx",
    "yaml",
    "neo4j",
    "numpy",
    "prometheus_client",
    "pydantic_settings",
):
    pytest.importorskip(_mod)


def test_audit_entry_on_policy_violation(tmp_path, monkeypatch):
    monkeypatch.setenv("UME_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UME_AGENT_ID", "tester")
    import importlib
    import ume

    importlib.reload(ume.config)
    importlib.reload(ume.audit)
    importlib.reload(ume.plugins.alignment)
    importlib.reload(ume.plugins.alignment.sample_policy)  # type: ignore[attr-defined]
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
    assert "forbidden" in str(entries[-1]["reason"])


def test_audit_entry_on_redactions(tmp_path, monkeypatch):
    monkeypatch.setenv("UME_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UME_AGENT_ID", "redactor")
    import importlib
    import ume

    importlib.reload(ume.config)
    importlib.reload(ume.audit)
    importlib.reload(ume.plugins.alignment)
    importlib.reload(ume.plugins.alignment.sample_policy)  # type: ignore[attr-defined]
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
    assert str(entries[-2]["reason"]).startswith("redact_node")
    assert str(entries[-1]["reason"]).startswith("redact_edge")
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


def test_s3_read_logs_error(monkeypatch, caplog):
    """Errors reading from S3 should be logged and return an empty list."""
    import sys
    import importlib
    import types

    class DummyClient:
        def get_object(self, *args, **kwargs):  # pragma: no cover - stub
            raise Exception("boom")

    dummy_boto3 = types.SimpleNamespace(client=lambda name: DummyClient())
    dummy_exceptions = types.SimpleNamespace(BotoCoreError=Exception, ClientError=Exception)
    monkeypatch.setitem(sys.modules, "boto3", dummy_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", dummy_exceptions)

    import ume.audit as audit
    importlib.reload(audit)

    with caplog.at_level("ERROR"):
        assert audit._read_lines("s3://bucket/key") == []
    assert any(
        "BotoCoreError while reading audit log from s3://bucket/key" in rec.message
        for rec in caplog.records
    )


def test_s3_read_logs_boto_core_error(monkeypatch, caplog):
    """BotoCoreError reading from S3 is logged and results in an empty list."""
    import sys
    import importlib
    import types

    class BotoErr(Exception):
        pass

    class DummyClient:
        def get_object(self, *args, **kwargs):
            raise BotoErr("boom")

    dummy_boto3 = types.SimpleNamespace(client=lambda name: DummyClient())
    dummy_exceptions = types.SimpleNamespace(BotoCoreError=BotoErr, ClientError=Exception)
    monkeypatch.setitem(sys.modules, "boto3", dummy_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", dummy_exceptions)

    import ume.audit as audit
    importlib.reload(audit)

    with caplog.at_level("ERROR"):
        assert audit._read_lines("s3://bucket/key") == []
    assert any(
        "BotoCoreError while reading audit log from s3://bucket/key" in rec.message
        for rec in caplog.records
    )


def test_s3_read_logs_client_error(monkeypatch, caplog):
    """ClientError reading from S3 is logged and results in an empty list."""
    import sys
    import importlib
    import types

    class ClientErr(Exception):
        pass

    class DummyClient:
        def get_object(self, *args, **kwargs):
            raise ClientErr("boom")

    class BotoDummy(Exception):
        pass

    dummy_boto3 = types.SimpleNamespace(client=lambda name: DummyClient())
    dummy_exceptions = types.SimpleNamespace(BotoCoreError=BotoDummy, ClientError=ClientErr)
    monkeypatch.setitem(sys.modules, "boto3", dummy_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", dummy_exceptions)

    import ume.audit as audit
    importlib.reload(audit)

    with caplog.at_level("ERROR"):
        assert audit._read_lines("s3://bucket/key") == []
    assert any(
        "ClientError while reading audit log from s3://bucket/key" in rec.message
        for rec in caplog.records
    )


def test_s3_write_logs_boto_core_error(monkeypatch, caplog):
    """BotoCoreError writing to S3 should be logged and raised."""
    import sys
    import importlib
    import types

    class BotoErr(Exception):
        pass

    class DummyClient:
        def put_object(self, *args, **kwargs):
            raise BotoErr("boom")

    dummy_boto3 = types.SimpleNamespace(client=lambda name: DummyClient())
    dummy_exceptions = types.SimpleNamespace(BotoCoreError=BotoErr, ClientError=Exception)
    monkeypatch.setitem(sys.modules, "boto3", dummy_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", dummy_exceptions)

    import ume.audit as audit
    importlib.reload(audit)

    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError):
            audit._write_lines("s3://bucket/key", ["x"])
    assert any(
        "BotoCoreError while writing audit log to s3://bucket/key" in rec.message
        for rec in caplog.records
    )


def test_s3_write_logs_client_error(monkeypatch, caplog):
    """ClientError writing to S3 should be logged and raised."""
    import sys
    import importlib
    import types

    class ClientErr(Exception):
        pass

    class DummyClient:
        def put_object(self, *args, **kwargs):
            raise ClientErr("boom")

    class BotoDummy(Exception):
        pass

    dummy_boto3 = types.SimpleNamespace(client=lambda name: DummyClient())
    dummy_exceptions = types.SimpleNamespace(BotoCoreError=BotoDummy, ClientError=ClientErr)
    monkeypatch.setitem(sys.modules, "boto3", dummy_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", dummy_exceptions)

    import ume.audit as audit
    importlib.reload(audit)

    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError):
            audit._write_lines("s3://bucket/key", ["x"])
    assert any(
        "ClientError while writing audit log to s3://bucket/key" in rec.message
        for rec in caplog.records
    )


def test_parse_s3_valid() -> None:
    from ume.audit import _parse_s3

    bucket, key = _parse_s3("s3://my-bucket/path/to/key")
    assert bucket == "my-bucket"
    assert key == "path/to/key"


@pytest.mark.parametrize(
    "path",
    [
        "bucket/key",  # missing scheme
        "s3://bucket",  # missing key
        "gs://bucket/key",  # wrong scheme
    ],
)
def test_parse_s3_invalid(path: str) -> None:
    from ume.audit import _parse_s3

    with pytest.raises(ValueError):
        _parse_s3(path)


def test_write_lines_creates_directory(tmp_path):
    from ume.audit import _write_lines, _read_lines

    path = tmp_path / "subdir" / "audit.log"
    _write_lines(str(path), ["entry1"])

    assert path.exists()
    assert _read_lines(str(path)) == ["entry1"]
