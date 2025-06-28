# mypy: ignore-errors
from __future__ import annotations
# ruff: noqa: E402

import sys
import types
from pathlib import Path

import pytest
import sqlite3
import time
import logging
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pkg_root = Path(__file__).resolve().parents[1] / "src" / "ume"
if "ume" not in sys.modules:
    stub = types.ModuleType("ume")
    stub.__path__ = [str(pkg_root)]
    sys.modules["ume"] = stub

from ume.config import settings
from ume.persistent_graph import PersistentGraph
from ume.retention import (
    start_retention_scheduler,
    stop_retention_scheduler,
    start_vector_age_scheduler,
    stop_vector_age_scheduler,
    _check_stale_vectors,
)
import ume.retention as retention
from ume.metrics import STALE_VECTOR_WARNINGS


def test_retention_scheduler_purges_records(monkeypatch) -> None:
    orig_connect = sqlite3.connect

    def _connect(*a, **kw):  # type: ignore[no-redef]
        return orig_connect(*a, check_same_thread=False, **kw)

    monkeypatch.setattr(sqlite3, "connect", _connect)  # type: ignore[arg-type]


    graph = PersistentGraph(":memory:")
    graph.add_node("old", {})
    graph.add_node("new", {})
    graph.add_edge("old", "new", "L")

    old_ts = int(time.time()) - 10
    with graph.conn:
        graph.conn.execute("UPDATE nodes SET created_at=? WHERE id='old'", (old_ts,))
        graph.conn.execute("UPDATE edges SET created_at=?", (old_ts,))

    monkeypatch.setattr(settings, "UME_GRAPH_RETENTION_DAYS", 0)
    start_retention_scheduler(graph, interval_seconds=0.01)
    time.sleep(0.02)
    stop_retention_scheduler()

    assert not graph.node_exists("old")
    assert graph.node_exists("new")
    assert graph.get_all_edges() == []


def test_retention_scheduler_reuses_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = types.SimpleNamespace(purge_old_records=lambda *a, **k: None)
    thread1, stop1 = start_retention_scheduler(graph, interval_seconds=0.01)
    thread2, stop2 = start_retention_scheduler(graph, interval_seconds=0.01)
    try:
        assert thread1 is thread2
    finally:
        stop1()
        stop_retention_scheduler()


def test_retention_scheduler_continues_after_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[None] = []
    def purge(_):
        calls.append(None)
        raise RuntimeError("fail")
    graph = types.SimpleNamespace(purge_old_records=purge)
    monkeypatch.setattr(settings, "UME_GRAPH_RETENTION_DAYS", 0)
    thread, stop = start_retention_scheduler(graph, interval_seconds=0.01)
    time.sleep(0.03)
    stop()
    stop_retention_scheduler()
    assert len(calls) > 1


def test_vector_age_scheduler_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    now = int(time.time())
    store = types.SimpleNamespace(
        get_vector_timestamps=lambda: {"old": now - 100, "new": now}
    )
    monkeypatch.setattr(settings, "UME_VECTOR_MAX_AGE_DAYS", 0)
    STALE_VECTOR_WARNINGS._value.set(0)  # type: ignore[attr-defined]
    thread, stop = start_vector_age_scheduler(
        store, interval_seconds=0.01, warn_threshold=0
    )
    time.sleep(0.02)
    stop()
    stop_vector_age_scheduler()
    assert STALE_VECTOR_WARNINGS._value.get() > 0


def test_stop_schedulers_without_start() -> None:
    stop_retention_scheduler()
    stop_vector_age_scheduler()


def test_check_stale_vectors_logs(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    now = int(time.time())
    store = types.SimpleNamespace(get_vector_timestamps=lambda: {"old": now - 100})
    monkeypatch.setattr(settings, "UME_VECTOR_MAX_AGE_DAYS", 0)
    STALE_VECTOR_WARNINGS._value.set(0)  # type: ignore[attr-defined]
    with caplog.at_level(logging.WARNING):
        _check_stale_vectors(store, log=True, threshold=0)
    assert STALE_VECTOR_WARNINGS._value.get() == 1
    assert "stale vectors detected" in caplog.text


def test_vector_age_scheduler_continues_after_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[None] = []

    def bad() -> dict[str, int]:
        calls.append(None)
        raise RuntimeError("boom")

    store = types.SimpleNamespace(get_vector_timestamps=bad)
    thread, stop = start_vector_age_scheduler(store, interval_seconds=0.01)
    time.sleep(0.03)
    stop()
    stop_vector_age_scheduler()
    assert len(calls) > 1


def test_start_retention_scheduler_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[None] = []

    def purge(_: int) -> None:
        calls.append(None)
        raise RuntimeError("fail")

    graph = types.SimpleNamespace(purge_old_records=purge)
    monkeypatch.setattr(settings, "UME_GRAPH_RETENTION_DAYS", 0)

    class DummyEvent:
        def __init__(self) -> None:
            self.count = 0
        def wait(self, timeout: float) -> bool:
            self.count += 1
            return self.count > 1
        def set(self) -> None:
            pass

    class DummyThread:
        def __init__(self, target: Callable[[], None], daemon: bool = False) -> None:
            self.target = target
            self.started = False
        def start(self) -> None:
            self.started = True
            self.target()
        def join(self) -> None:
            self.started = False
        def is_alive(self) -> bool:
            return self.started

    monkeypatch.setattr(retention, "threading", types.SimpleNamespace(Thread=DummyThread, Event=DummyEvent))
    thread, stop = start_retention_scheduler(graph, interval_seconds=0.01)
    stop()
    assert len(calls) == 2


def test_vector_age_scheduler_reuses_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    store = types.SimpleNamespace(get_vector_timestamps=lambda: {})

    class DummyEvent:
        def __init__(self) -> None:
            self.count = 0
        def wait(self, timeout: float) -> bool:
            self.count += 1
            return self.count > 1
        def set(self) -> None:
            pass

    class DummyThread:
        def __init__(self, target: Callable[[], None], daemon: bool = False) -> None:
            self.target = target
            self.started = False
        def start(self) -> None:
            self.started = True
            self.target()
        def join(self) -> None:
            self.started = False
        def is_alive(self) -> bool:
            return self.started

    monkeypatch.setattr(retention, "threading", types.SimpleNamespace(Thread=DummyThread, Event=DummyEvent))
    thread1, stop1 = start_vector_age_scheduler(store, interval_seconds=0.01)
    thread2, stop2 = start_vector_age_scheduler(store, interval_seconds=0.01)
    stop1()
    stop_vector_age_scheduler()
    assert thread1 is thread2
