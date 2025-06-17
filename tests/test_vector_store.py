import time
import importlib
from ume import Event, EventType, MockGraph, apply_event_to_graph
from ume.vector_store import VectorStore, VectorStoreListener
from ume._internal.listeners import register_listener, unregister_listener
import faiss
import pytest


def test_vector_store_add_and_query_cpu() -> None:
    store = VectorStore(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])
    store.add("b", [0.0, 1.0])
    res = store.query([1.0, 0.0], k=1)
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


def test_vector_store_env_gpu(monkeypatch) -> None:
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


def test_vector_store_gpu_mem_setting(monkeypatch) -> None:
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
