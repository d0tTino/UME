# ruff: noqa: E402
import time
from pathlib import Path
import sys
import types
import pytest

faiss = pytest.importorskip("faiss")
if not hasattr(faiss, "IndexFlatL2"):
    pytest.skip("faiss is missing required functionality", allow_module_level=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ume import Event, EventType, MockGraph, apply_event_to_graph
from ume.vector_store import FaissBackend, ChromaBackend, VectorStoreListener
from ume.api import configure_vector_store, app
from ume._internal.listeners import register_listener, unregister_listener
from prometheus_client import Gauge, Histogram
import logging
import threading


@pytest.fixture(params=[FaissBackend, ChromaBackend])
def store_cls(request):
    return request.param


def test_vector_store_add_and_query_cpu(store_cls) -> None:
    store = store_cls(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])
    store.add("b", [0.0, 1.0])
    res = store.query([1.0, 0.0], k=1)
    assert res == ["a"]


def test_vector_store_update_existing(store_cls) -> None:
    store = store_cls(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])
    store.add("a", [0.0, 1.0])
    res = store.query([0.0, 1.0], k=1)
    assert res == ["a"]


def test_vector_store_update_existing_gpu(store_cls) -> None:
    if not hasattr(faiss, "StandardGpuResources"):
        pytest.skip("FAISS GPU not available")
    if store_cls is not FaissBackend:
        pytest.skip("GPU only supported for FAISS backend")
    store = store_cls(dim=2, use_gpu=True)
    store.add("a", [1.0, 0.0])
    store.add("a", [0.0, 1.0])
    res = store.query([0.0, 1.0], k=1)
    assert res == ["a"]


def test_vector_store_listener_on_create(store_cls) -> None:
    store = store_cls(dim=2, use_gpu=False)
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


def test_vector_store_gpu_init(store_cls) -> None:
    if not hasattr(faiss, "StandardGpuResources"):
        pytest.skip("FAISS GPU not available")
    if store_cls is not FaissBackend:
        pytest.skip("GPU only supported for FAISS backend")
    store_cls(dim=2, use_gpu=True)


def test_vector_store_env_gpu(monkeypatch: pytest.MonkeyPatch, store_cls) -> None:
    if not hasattr(faiss, "StandardGpuResources"):
        pytest.skip("FAISS GPU not available")
    if store_cls is not FaissBackend:
        pytest.skip("GPU only supported for FAISS backend")

    monkeypatch.setenv("UME_VECTOR_USE_GPU", "true")
    import importlib
    import ume.config as cfg
    import ume.vector_store as vs

    importlib.reload(cfg)
    importlib.reload(vs)

    store = vs.FaissBackend(dim=2)
    assert store.gpu_resources is not None


def test_vector_store_gpu_mem_setting(monkeypatch: pytest.MonkeyPatch, store_cls) -> None:
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

    store = vs.FaissBackend(dim=2)
    assert isinstance(store.gpu_resources, DummyRes)
    assert store.gpu_resources.temp == 1 * 1024 * 1024


def test_vector_store_save_and_load(tmp_path: Path, store_cls) -> None:
    path = tmp_path / "index.faiss"
    store = store_cls(dim=2, use_gpu=False, path=str(path))
    store.add("x", [1.0, 0.0])
    store.save()

    new_store = store_cls(dim=2, use_gpu=False)
    new_store.load(str(path))

    assert new_store.query([1.0, 0.0], k=1) == ["x"]


def test_vector_store_add_persist(tmp_path: Path, store_cls) -> None:
    path = tmp_path / "persist.faiss"
    store = store_cls(dim=2, use_gpu=False, path=str(path))
    store.add("y", [1.0, 0.0], persist=True)

    new_store = store_cls(dim=2, use_gpu=False)
    new_store.load(str(path))

    assert new_store.query([1.0, 0.0], k=1) == ["y"]


def test_vector_store_save_creates_directory(tmp_path: Path, store_cls) -> None:
    path = tmp_path / "nested" / "save.faiss"
    store = store_cls(dim=2, use_gpu=False, path=str(path))
    store.add("d", [1.0, 0.0])
    store.save()

    assert path.exists()


def test_vector_store_background_flush(tmp_path: Path, store_cls) -> None:
    path = tmp_path / "bg.faiss"
    store = store_cls(dim=2, use_gpu=False, path=str(path), flush_interval=0.01)
    store.add("z", [0.0, 1.0])
    time.sleep(0.02)
    store.close()

    new_store = store_cls(dim=2, use_gpu=False)
    new_store.load(str(path))

    assert new_store.query([0.0, 1.0], k=1) == ["z"]


def test_background_flush_continues_on_save_error(tmp_path: Path, store_cls) -> None:
    path = tmp_path / "err.faiss"
    store = store_cls(dim=2, use_gpu=False, path=str(path), flush_interval=0.01)

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
    time.sleep(0.03)
    store.close()

    assert calls >= 2
    new_store = store_cls(dim=2, use_gpu=False)
    new_store.load(str(path))
    assert new_store.query([1.0, 0.0], k=1) == ["c"]


def test_background_flush_retries_on_save_error(tmp_path: Path, caplog: pytest.LogCaptureFixture, store_cls) -> None:
    path = tmp_path / "retry.faiss"
    store = store_cls(dim=2, use_gpu=False, path=str(path), flush_interval=0.01)

    calls = 0
    orig_save = store.save

    def failing_save(p: str | None = None) -> None:
        nonlocal calls
        calls += 1
        if calls <= 3:
            raise RuntimeError("boom")
        orig_save(p)

    store.save = failing_save  # type: ignore[assignment]
    store.add("d", [1.0, 0.0])
    with caplog.at_level(logging.WARNING, logger="ume.vector_store"):
        time.sleep(0.05)
    store.close()

    assert calls >= 4
    assert any("retrying" in rec.message.lower() for rec in caplog.records)
    assert any("after 3 attempts" in rec.message for rec in caplog.records)
    new_store = store_cls(dim=2, use_gpu=False)
    new_store.load(str(path))
    assert new_store.query([1.0, 0.0], k=1) == ["d"]


def test_vector_store_metrics_init(store_cls) -> None:
    suffix = store_cls.__name__
    lat = Histogram(f"test_query_latency_{suffix}", "desc")
    size = Gauge(f"test_index_size_{suffix}", "desc")
    store = store_cls(
        dim=2,
        use_gpu=False,
        query_latency_metric=lat,
        index_size_metric=size,
    )
    assert store.query_latency_metric is lat
    assert store.index_size_metric is size


def test_configure_vector_store_replacement_closes_existing(tmp_path: Path, store_cls) -> None:
    path = tmp_path / "old.faiss"
    store1 = store_cls(dim=2, use_gpu=False, path=str(path), flush_interval=0.01)
    configure_vector_store(store1)
    # Allow background thread to start
    time.sleep(0.02)

    store2 = store_cls(dim=2, use_gpu=False)
    configure_vector_store(store2)

    assert store1._flush_thread is None
    assert app.state.vector_store is store2
    store2.close()


def test_configure_vector_store_close_error(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, store_cls) -> None:
    store1 = store_cls(dim=2, use_gpu=False)
    configure_vector_store(store1)

    def boom() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(store1, "close", boom)
    store2 = store_cls(dim=2, use_gpu=False)
    with caplog.at_level("ERROR"):
        configure_vector_store(store2)
    assert app.state.vector_store is store2
    assert any(
        "Failed to close existing vector store" in rec.getMessage()
        for rec in caplog.records
    )


def test_concurrent_add_and_query(store_cls) -> None:
    store = store_cls(dim=2, use_gpu=False)

    def adder(prefix: str) -> None:
        for i in range(50):
            store.add(f"{prefix}-{i}", [float(i), 0.0])

    def querier() -> None:
        for _ in range(100):
            store.query([0.0, 0.0])

    threads = [threading.Thread(target=adder, args=(str(i),)) for i in range(5)]
    threads += [threading.Thread(target=querier) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(store.idx_to_id) == 250


def test_concurrent_add_with_background_flush(tmp_path: Path, store_cls) -> None:
    path = tmp_path / "concurrent.faiss"
    store = store_cls(dim=2, use_gpu=False, path=str(path), flush_interval=0.01)

    def worker(i: int) -> None:
        store.add(f"id-{i}", [float(i), 0.0])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    time.sleep(0.02)
    store.close()

    new_store = store_cls(dim=2, use_gpu=False)
    new_store.load(str(path))
    assert len(new_store.idx_to_id) == 20


def test_context_manager_stops_flush_thread(tmp_path: Path, store_cls) -> None:
    path = tmp_path / "cm.faiss"
    with store_cls(dim=2, use_gpu=False, path=str(path), flush_interval=0.05) as store:
        store.add("ctx", [1.0, 0.0])
        thread = store._flush_thread
        assert thread is not None and thread.is_alive()
    assert thread is not None and not thread.is_alive()


def test_add_many(store_cls) -> None:
    store = store_cls(dim=2, use_gpu=False)
    store.add_many({"a": [1.0, 0.0], "b": [0.0, 1.0]})
    assert set(store.query([1.0, 0.0], k=2)) == {"a", "b"}


def test_add_many_dimension_mismatch(store_cls) -> None:
    store = store_cls(dim=2, use_gpu=False)
    with pytest.raises(ValueError):
        store.add_many({"a": [1.0]})

class DummyModel:
    def __init__(self, dim: int) -> None:
        self.dim = dim
    def encode(self, text: str):
        import numpy as np
        return np.zeros(self.dim, dtype=float)


def test_create_default_store_dimension_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as m:
        m.setenv("UME_VECTOR_BACKEND", "chroma")
        m.setenv("UME_VECTOR_DIM", "2")
        dummy_module = types.SimpleNamespace(SentenceTransformer=lambda name: DummyModel(3))
        m.setitem(sys.modules, "sentence_transformers", dummy_module)
        sys.modules.pop("ume.embedding", None)
        import importlib
        import ume.config as cfg
        import ume.vector_store as vs
        importlib.reload(cfg)
        importlib.reload(vs)
        with pytest.raises(ValueError):
            vs.create_default_store()
    sys.modules.pop("ume.embedding", None)
    import importlib
    import ume.config as cfg
    import ume.vector_store as vs
    importlib.reload(cfg)
    importlib.reload(vs)


def test_create_default_store_dimension_autoset(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as m:
        m.setenv("UME_VECTOR_BACKEND", "chroma")
        m.setenv("UME_VECTOR_DIM", "0")
        dummy_module = types.SimpleNamespace(SentenceTransformer=lambda name: DummyModel(4))
        m.setitem(sys.modules, "sentence_transformers", dummy_module)
        sys.modules.pop("ume.embedding", None)
        import importlib
        import ume.config as cfg
        import ume.vector_store as vs
        importlib.reload(cfg)
        importlib.reload(vs)
        store = vs.create_default_store()
        assert cfg.settings.UME_VECTOR_DIM == 4
        assert store.dim == 4
    sys.modules.pop("ume.embedding", None)
    import importlib
    import ume.config as cfg
    import ume.vector_store as vs
    importlib.reload(cfg)
    importlib.reload(vs)
