import logging
import pathlib
from ume.auto_snapshot import enable_snapshot_autosave_and_restore
from ume import PersistentGraph


def test_enable_snapshot_autosave_logs_warning(tmp_path, caplog, monkeypatch):
    snapshot_file = tmp_path / "snapshot.json"
    snapshot_file.write_text("{}")
    graph = PersistentGraph(":memory:")

    import ume.auto_snapshot as auto_snapshot

    def raise_error(*args, **kwargs):
        raise ValueError("load error")

    monkeypatch.setattr(auto_snapshot, "load_graph_into_existing", raise_error)
    monkeypatch.setattr(auto_snapshot, "enable_periodic_snapshot", lambda *args, **kwargs: None)

    with caplog.at_level(logging.WARNING):
        auto_snapshot.enable_snapshot_autosave_and_restore(graph, snapshot_file)

    assert any(
        "Failed to restore snapshot" in rec.message for rec in caplog.records
    )

