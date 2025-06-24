# mypy: ignore-errors
from __future__ import annotations

import sys
from pathlib import Path
import pytest
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import time
import pytest
import types

from ume.persistent_graph import PersistentGraph
import sqlite3
from ume.config import settings
from ume.retention import start_retention_scheduler, stop_retention_scheduler


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
    start_retention_scheduler(graph, interval_seconds=0.05)
    time.sleep(0.1)
    stop_retention_scheduler()

    assert not graph.node_exists("old")
    assert graph.node_exists("new")
    assert graph.get_all_edges() == []


def test_retention_scheduler_reuses_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = types.SimpleNamespace(purge_old_records=lambda *a, **k: None)
    thread1, stop1 = start_retention_scheduler(graph, interval_seconds=0.1)
    thread2, stop2 = start_retention_scheduler(graph, interval_seconds=0.1)
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
    thread, stop = start_retention_scheduler(graph, interval_seconds=0.05)
    time.sleep(0.12)
    stop()
    stop_retention_scheduler()
    assert len(calls) > 1
