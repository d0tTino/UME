# mypy: ignore-errors
from ume.memory import EpisodicMemory, SemanticMemory, ColdMemory
from ume.config import settings
from ume.metrics import STALE_VECTOR_WARNINGS
from ume.memory.tiered import TieredMemoryManager
from ume.memory_aging import start_memory_aging_scheduler, stop_memory_aging_scheduler

import time
import pytest


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Speed up tests by removing sleep delays."""
    monkeypatch.setattr(time, "sleep", lambda _: None)


def test_memory_aging_moves_old_events(monkeypatch: pytest.MonkeyPatch) -> None:
    episodic = EpisodicMemory(db_path=":memory:")
    semantic = SemanticMemory(db_path=":memory:")
    episodic.graph.add_node("old", {"text": "hi"})
    old_ts = int(time.time()) - 10
    with episodic.graph.conn:
        episodic.graph.conn.execute(
            "UPDATE nodes SET created_at=? WHERE id='old'", (old_ts,)
        )

    mgr = TieredMemoryManager(
        episodic,
        semantic,
        cold=None,
        event_age_seconds=0,
        cold_age_seconds=None,
        vector_check_interval=0.01,
    )
    mgr.start(interval_seconds=0.01)
    time.sleep(0.02)
    mgr.stop()

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


def test_cold_memory_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    episodic = EpisodicMemory(db_path=":memory:")
    semantic = SemanticMemory(db_path=":memory:")
    cold = ColdMemory(db_path=":memory:")

    episodic.graph.add_node("cold", {"text": "bye"})
    old_ts = int(time.time()) - 10
    with episodic.graph.conn:
        episodic.graph.conn.execute(
            "UPDATE nodes SET created_at=? WHERE id='cold'",
            (old_ts,),
        )

    mgr = TieredMemoryManager(
        episodic,
        semantic,
        cold=cold,
        event_age_seconds=0,
        cold_age_seconds=0,
        vector_check_interval=0.01,
    )
    mgr.start(interval_seconds=0.01)
    time.sleep(0.02)
    mgr.stop()

    assert cold.get_item("cold") == {"text": "bye"}
    assert not semantic.get_fact("cold")


def test_vector_freshness_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    now = int(time.time())

    class DummyStore:
        def expire_vectors(self, *_: object) -> None:
            pass

        def get_vector_timestamps(self) -> dict[str, int]:
            return {"old": now - 100}

    store = DummyStore()
    episodic = EpisodicMemory(db_path=":memory:")
    semantic = SemanticMemory(db_path=":memory:")

    monkeypatch.setattr(settings, "UME_VECTOR_MAX_AGE_DAYS", 0, raising=False)
    STALE_VECTOR_WARNINGS._value.set(0)  # type: ignore[attr-defined]

    mgr = TieredMemoryManager(
        episodic,
        semantic,
        cold=None,
        vector_store=store,
        event_age_seconds=0,
        vector_age_seconds=0,
        vector_check_interval=0.0,
    )
    mgr.start(interval_seconds=0.01)
    time.sleep(0.02)
    mgr.stop()

    assert STALE_VECTOR_WARNINGS._value.get() > 0  # type: ignore[attr-defined]


def test_scheduler_singleton_and_cleanup() -> None:
    """Scheduler start calls reuse the thread and cleanup works."""
    episodic = EpisodicMemory(db_path=":memory:")
    semantic = SemanticMemory(db_path=":memory:")

    thread1, _ = start_memory_aging_scheduler(
        episodic,
        semantic,
        cold=None,
        event_age_seconds=0,
        cold_age_seconds=None,
        interval_seconds=0.01,
        vector_check_interval=0.01,
    )

    thread2, _ = start_memory_aging_scheduler(
        episodic,
        semantic,
        cold=None,
        event_age_seconds=0,
        cold_age_seconds=None,
        interval_seconds=0.01,
        vector_check_interval=0.01,
    )


    assert thread1 is thread2
    assert thread1.is_alive()

    stop_memory_aging_scheduler()
    assert not thread1.is_alive()

    import ume.memory_aging as aging

    assert aging._thread is None
    assert aging._stop_event is None

    thread3, _ = start_memory_aging_scheduler(
        episodic,
        semantic,
        cold=None,
        event_age_seconds=0,
        cold_age_seconds=None,
        interval_seconds=0.01,
        vector_check_interval=0.01,
    )

    assert thread3 is not thread1

    stop_memory_aging_scheduler()
    assert not thread3.is_alive()
