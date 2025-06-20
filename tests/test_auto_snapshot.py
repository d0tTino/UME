import logging
from typing import Callable
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


def test_disable_unregisters_atexit_handle(monkeypatch, tmp_path):
    import ume.auto_snapshot as auto_snapshot

    registered: list[Callable] = []

    def fake_register(func):
        registered.append(func)
        return func

    def fake_unregister(func):
        registered.remove(func)

    monkeypatch.setattr(auto_snapshot.atexit, "register", fake_register)
    monkeypatch.setattr(auto_snapshot.atexit, "unregister", fake_unregister)

    class DummyEvent:
        def wait(self, timeout: float | None = None) -> bool:
            return True

        def set(self) -> None:
            pass

    class DummyThread:
        def __init__(self, target=None, daemon=None) -> None:
            self._target = target

        def start(self) -> None:
            pass

        def join(self) -> None:
            pass

    monkeypatch.setattr(auto_snapshot.threading, "Event", DummyEvent)
    monkeypatch.setattr(auto_snapshot.threading, "Thread", DummyThread)

    graph = PersistentGraph(":memory:")

    auto_snapshot.enable_periodic_snapshot(graph, tmp_path / "snap.json", 1)
    assert len(registered) == 1

    auto_snapshot.disable_periodic_snapshot()

    assert registered == []
    assert auto_snapshot._atexit_handle is None


def test_unregistering_prevents_multiple_snapshots(monkeypatch, tmp_path):
    import ume.auto_snapshot as auto_snapshot

    handles: list[Callable] = []

    def fake_register(func):
        handles.append(func)
        return func

    def fake_unregister(func):
        handles.remove(func)

    monkeypatch.setattr(auto_snapshot.atexit, "register", fake_register)
    monkeypatch.setattr(auto_snapshot.atexit, "unregister", fake_unregister)

    class DummyEvent:
        def wait(self, timeout: float | None = None) -> bool:
            return True

        def set(self) -> None:
            pass

    class DummyThread:
        def __init__(self, target=None, daemon=None) -> None:
            self._target = target

        def start(self) -> None:
            pass

        def join(self) -> None:
            pass

    monkeypatch.setattr(auto_snapshot.threading, "Event", DummyEvent)
    monkeypatch.setattr(auto_snapshot.threading, "Thread", DummyThread)

    calls = []

    def fake_snapshot(*args, **kwargs):
        calls.append(1)

    monkeypatch.setattr(auto_snapshot, "snapshot_graph_to_file", fake_snapshot)

    graph = PersistentGraph(":memory:")

    auto_snapshot.enable_periodic_snapshot(graph, tmp_path / "a.json", 1)
    auto_snapshot.disable_periodic_snapshot()
    auto_snapshot.enable_periodic_snapshot(graph, tmp_path / "b.json", 1)
    auto_snapshot.disable_periodic_snapshot()

    for func in handles[:]:
        func()

    assert calls == []
    assert handles == []
