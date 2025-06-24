import time
import importlib.util
import sys
import types
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "src" / "ume"

ume_pkg = types.ModuleType("ume")
ume_pkg.__path__ = [str(BASE)]
sys.modules["ume"] = ume_pkg

def _load(name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(f"ume.{name}", BASE / f"{name}.py")
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"ume.{name}"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

pg = _load("persistent_graph")
cfg = _load("config")
ret = _load("retention")

PersistentGraph = pg.PersistentGraph
settings = cfg.settings
start_retention_scheduler = ret.start_retention_scheduler
stop_retention_scheduler = ret.stop_retention_scheduler


def test_retention_scheduler_purges_records(monkeypatch) -> None:
    # Allow SQLite connection across threads for the retention scheduler
    orig_connect = pg.sqlite3.connect
    monkeypatch.setattr(pg.sqlite3, "connect", lambda *a, **kw: orig_connect(*a, check_same_thread=False, **kw))

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


def test_retention_scheduler_reuses_thread(monkeypatch):
    graph = types.SimpleNamespace(purge_old_records=lambda *a, **k: None)
    thread1, stop1 = start_retention_scheduler(graph, interval_seconds=0.1)
    thread2, stop2 = start_retention_scheduler(graph, interval_seconds=0.1)
    try:
        assert thread1 is thread2
    finally:
        stop1()
        stop_retention_scheduler()


def test_retention_scheduler_continues_after_error(monkeypatch):
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
