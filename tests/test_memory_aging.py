# mypy: ignore-errors
from ume.memory import EpisodicMemory, SemanticMemory
from ume.memory_aging import (
    start_memory_aging_scheduler,
    stop_memory_aging_scheduler,
)

import sqlite3
import time
import pytest


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Speed up tests by removing sleep delays."""
    monkeypatch.setattr(time, "sleep", lambda _: None)


def test_memory_aging_moves_old_events(monkeypatch: pytest.MonkeyPatch) -> None:
    orig_connect = sqlite3.connect

    def _connect(*a, **kw):  # type: ignore[no-redef]
        return orig_connect(*a, check_same_thread=False, **kw)

    monkeypatch.setattr(sqlite3, "connect", _connect)  # type: ignore[arg-type]

    episodic = EpisodicMemory(db_path=":memory:")
    semantic = SemanticMemory(db_path=":memory:")
    episodic.graph.add_node("old", {"text": "hi"})
    old_ts = int(time.time()) - 10
    with episodic.graph.conn:
        episodic.graph.conn.execute(
            "UPDATE nodes SET created_at=? WHERE id='old'", (old_ts,)
        )

    start_memory_aging_scheduler(
        episodic,
        semantic,
        event_age_seconds=0,
        interval_seconds=0.01,
    )
    time.sleep(0.02)
    stop_memory_aging_scheduler()

    assert not episodic.graph.node_exists("old")
    assert semantic.get_fact("old") == {"text": "hi"}


def test_vector_store_expire_vectors() -> None:
    pytest.importorskip("faiss")
    from ume.vector_store import VectorStore

    store = VectorStore(dim=2, use_gpu=False)
    store.add("x", [0.0, 1.0])
    store.vector_ts["x"] = int(time.time()) - 10
    store.expire_vectors(5)
    assert store.query([0.0, 1.0], k=1) == []
