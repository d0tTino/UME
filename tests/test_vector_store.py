import time
from ume import Event, EventType, MockGraph, apply_event_to_graph
from ume.vector_store import VectorStore, VectorStoreListener
from ume.api import configure_vector_store, app
from ume._internal.listeners import register_listener, unregister_listener
import faiss
import pytest
from pathlib import Path
from typing import Any
from prometheus_client import Gauge, Histogram


def test_vector_store_add_and_query_cpu() -> None:
    store = VectorStore(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])
    store.add("b", [0.0, 1.0])
    res = store.query([1.0, 0.0], k=1)
    assert res == ["a"]


def test_vector_store_update_existing() -> None:
    store = VectorStore(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])
    store.add("a", [0.0, 1.0])
    res = store.query([0.0, 1.0], k=1)
    assert res == ["a"]


def test_vector_store_update_existing_gpu() -> None:
    if not hasattr(faiss, "StandardGpuResources"):
        pytest.skip("FAISS GPU not available")
    store = VectorStore(dim=2, use_gpu=True)
    store.add("a", [1.0, 0.0])
    store.add("a", [0.0, 1.0])
    res = store.query([0.0, 1.0], k=1)
    assert res == ["a"]


def test_vector_store_listener_on_create() -> None:
    store = VectorStore(dim=2, use_gpu=False)
    listener = VectorStoreListener(store)
    register_listener(listener)
    graph = MockGraph()
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"node_id": "n1", "attributes": {"embedding": [1.0, 0.0]}},
    )
    apply_event_to_graph(event, graph)
    unregister_listener(listener)

    assert store.query([1.0, 0.0], k=1) == ["n1"]


def test_vector_store_gpu_init() -> None:
    if not hasattr(faiss, "StandardGpuResources"):
        pytest.skip("FAISS GPU not available")
    VectorStore(dim=2, use_gpu=True)


def test_vector_store_env_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    if not hasattr(faiss, "StandardGpuResources"):
        pytest.skip("FAISS GPU not available")

    monkeypatch.setenv("UME_VECTOR_USE_GPU", "true")
    import importlib
    import ume.config as cfg
    import ume.vector_store as vs

    importlib.reload(cfg)
    importlib.reload(vs)

    store = vs.VectorStore(dim=2)
    assert store.gpu_resources is not None


def test_vector_store_gpu_mem_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    if not hasattr(faiss, "StandardGpuResources"):
        pytest.skip("FAISS GPU not available")

    class DummyRes:
        def __init__(self) -> None:
            self.temp: int | None = None

        def setTempMemory(self, value: int) -> None:  # noqa: N802
            self.temp = value

    monkeypatch.setenv("UME_VECTOR_USE_GPU", "true")
    monkeypatch.setenv("UME_VECTOR_GPU_MEM_MB", "1")
    monkeypatch.setattr(faiss, "StandardGpuResources", DummyRes)
    monkeypatch.setattr(faiss, "index_cpu_to_gpu", lambda res, _, idx: idx)

    import importlib

    import ume.config as cfg
    import ume.vector_store as vs

    importlib.reload(cfg)
    importlib.reload(vs)

    store = vs.VectorStore(dim=2)
    assert isinstance(store.gpu_resources, DummyRes)
    assert store.gpu_resources.temp == 1 * 1024 * 1024


def test_vector_store_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "index.faiss"
    store = VectorStore(dim=2, use_gpu=False, path=str(path))
    store.add("x", [1.0, 0.0])
    store.save()

    new_store = VectorStore(dim=2, use_gpu=False)
    new_store.load(str(path))

    assert new_store.query([1.0, 0.0], k=1) == ["x"]


def test_vector_store_add_persist(tmp_path: Path) -> None:
    path = tmp_path / "persist.faiss"
    store = VectorStore(dim=2, use_gpu=False, path=str(path))
    store.add("y", [1.0, 0.0], persist=True)

    new_store = VectorStore(dim=2, use_gpu=False)
    new_store.load(str(path))

    assert new_store.query([1.0, 0.0], k=1) == ["y"]


def test_vector_store_save_creates_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "save.faiss"
    store = VectorStore(dim=2, use_gpu=False, path=str(path))
    store.add("d", [1.0, 0.0])
    store.save()

    assert path.exists()


def test_vector_store_background_flush(tmp_path: Path) -> None:
    path = tmp_path / "bg.faiss"
    store = VectorStore(dim=2, use_gpu=False, path=str(path), flush_interval=0.1)
    store.add("z", [0.0, 1.0])
    time.sleep(0.2)
    store.stop_background_flush()

    new_store = VectorStore(dim=2, use_gpu=False)
    new_store.load(str(path))

    assert new_store.query([0.0, 1.0], k=1) == ["z"]


def test_background_flush_continues_on_save_error(tmp_path: Path) -> None:
    path = tmp_path / "err.faiss"
    store = VectorStore(dim=2, use_gpu=False, path=str(path), flush_interval=0.05)

    calls = 0
    orig_save = store.save

    def failing_save(p: str | None = None) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        orig_save(p)

    store.save = failing_save  # type: ignore[assignment]
    store.add("c", [1.0, 0.0])
    time.sleep(0.15)
    store.stop_background_flush()

    assert calls >= 2
    new_store = VectorStore(dim=2, use_gpu=False)
    new_store.load(str(path))
    assert new_store.query([1.0, 0.0], k=1) == ["c"]


def test_vector_store_metrics_init() -> None:
    lat = Histogram("test_query_latency", "desc")
    size = Gauge("test_index_size", "desc")
    store = VectorStore(
        dim=2,
        use_gpu=False,
        query_latency_metric=lat,
        index_size_metric=size,
    )
    assert store.query_latency_metric is lat
    assert store.index_size_metric is size


def test_configure_vector_store_replacement_closes_existing(tmp_path: Path) -> None:
    path = tmp_path / "old.faiss"
    store1 = VectorStore(dim=2, use_gpu=False, path=str(path), flush_interval=0.1)
    configure_vector_store(store1)
    # Allow background thread to start
    time.sleep(0.2)

    store2 = VectorStore(dim=2, use_gpu=False)
    configure_vector_store(store2)

    assert store1._flush_thread is None
    assert app.state.vector_store is store2
    store2.close()


@pytest.mark.parametrize(
    "vector",
    [
        "not a vector",
        [1.0, "a"],
        [[1.0, 2.0]],
    ],
)
def test_vector_store_query_invalid_input(vector: Any) -> None:
    store = VectorStore(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])

    with pytest.raises(ValueError, match="iterable of numbers"):
        store.query(vector)
