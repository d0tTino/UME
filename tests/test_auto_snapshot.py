import logging
from ume import PersistentGraph


def test_enable_snapshot_autosave_logs_warning(tmp_path, caplog, monkeypatch):
    snapshot_file = tmp_path / "snapshot.json"
    snapshot_file.write_text("{}")
    graph = PersistentGraph(":memory:")

    import ume.auto_snapshot as auto_snapshot

    def raise_error(*args, **kwargs):
        raise ValueError("load error")

    monkeypatch.setattr(auto_snapshot, "load_graph_into_existing", raise_error)
    sentinel_thread = object()
    sentinel_stop = object()
    monkeypatch.setattr(
        auto_snapshot,
        "enable_periodic_snapshot",
        lambda *args, **kwargs: (sentinel_thread, sentinel_stop),
    )

    with caplog.at_level(logging.WARNING, logger="ume.auto_snapshot"):
        result = auto_snapshot.enable_snapshot_autosave_and_restore(graph, snapshot_file)

    assert result == (sentinel_thread, sentinel_stop)
    assert any("Failed to restore snapshot" in rec.message for rec in caplog.records)


def test_periodic_snapshot_logs_error(tmp_path, caplog, monkeypatch):
    import ume.auto_snapshot as auto_snapshot

    graph = PersistentGraph(":memory:")
    snapshot_file = tmp_path / "snapshot.json"

    def raise_error(*args, **kwargs):
        raise ValueError("snap error")

    monkeypatch.setattr(auto_snapshot, "snapshot_graph_to_file", raise_error)

    events: dict[str, bool] = {}

    class DummyEvent:
        def __init__(self) -> None:
            self.calls = 0

        def wait(self, timeout: float | None = None) -> bool:
            self.calls += 1
            return self.calls > 1

        def set(self) -> None:
            events["set"] = True

    class DummyThread:
        def __init__(self, target=None, daemon=None) -> None:
            self._target = target

        def start(self) -> None:
            self._target()

        def join(self) -> None:
            events["joined"] = True

    monkeypatch.setattr(auto_snapshot.threading, "Event", DummyEvent)
    monkeypatch.setattr(auto_snapshot.threading, "Thread", DummyThread)

    with caplog.at_level(logging.ERROR, logger="ume.auto_snapshot"):
        auto_snapshot.enable_periodic_snapshot(graph, snapshot_file, 1)

    auto_snapshot.disable_periodic_snapshot()

    assert any("Failed to snapshot graph" in rec.message for rec in caplog.records)


def test_disable_periodic_snapshot(monkeypatch, tmp_path):
    import ume.auto_snapshot as auto_snapshot

    events: dict[str, bool] = {}

    class DummyEvent:
        def wait(self, timeout: float | None = None) -> bool:
            return False

        def set(self) -> None:
            events["set"] = True

    class DummyThread:
        def __init__(self, target=None, daemon=None) -> None:
            self._target = target

        def start(self) -> None:  # pragma: no cover - noop in test
            pass

        def join(self) -> None:
            events["joined"] = True

    monkeypatch.setattr(auto_snapshot.threading, "Event", DummyEvent)
    monkeypatch.setattr(auto_snapshot.threading, "Thread", DummyThread)

    graph = PersistentGraph(":memory:")
    thread, stop = auto_snapshot.enable_periodic_snapshot(graph, tmp_path / "snap.json", 1)
    auto_snapshot.disable_periodic_snapshot()

    assert events.get("set") and events.get("joined")
