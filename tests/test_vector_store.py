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


@pytest.mark.parametrize(
    "env_gpu",
    [False, True] if hasattr(faiss, "StandardGpuResources") else [False],
)
def test_vector_store_save_load(tmp_path, monkeypatch, env_gpu) -> None:
    if env_gpu:
        monkeypatch.setenv("UME_VECTOR_USE_GPU", "true")
    else:
        monkeypatch.setenv("UME_VECTOR_USE_GPU", "false")

    import ume.config as cfg
    import ume.vector_store as vs
    importlib.reload(cfg)
    importlib.reload(vs)

    store = vs.VectorStore(dim=2)
    store.add("a", [1.0, 0.0])
    index_path = tmp_path / "index.faiss"
    store.save(str(index_path))

    loaded = vs.VectorStore.load(str(index_path))
    assert loaded.query([1.0, 0.0], k=1) == ["a"]

