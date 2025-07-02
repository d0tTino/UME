# ruff: noqa: E402
import importlib.util
import sys
import types

from pathlib import Path

import pytest

faiss = pytest.importorskip("faiss")
if not hasattr(faiss, "IndexFlatL2"):
    pytest.skip("faiss is missing required functionality", allow_module_level=True)

pytest.importorskip(
    "prometheus_client", reason="prometheus_client is required for metrics"
)

root = Path(__file__).resolve().parents[1]


@pytest.fixture()
def vector_store_cls():
    orig_pkg = sys.modules.get("ume")
    orig_vs = sys.modules.get("ume.vector_store")
    package = types.ModuleType("ume")
    package.__path__ = [str(root / "src" / "ume")]
    sys.modules["ume"] = package

    spec = importlib.util.spec_from_file_location(
        "ume.vector_store",
        root / "src" / "ume" / "vector_store.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["ume.vector_store"] = module
    spec.loader.exec_module(module)

    setattr(package, "vector_store", module)
    try:
        yield module.VectorStore
    finally:
        if orig_vs is not None:
            sys.modules["ume.vector_store"] = orig_vs
        else:
            sys.modules.pop("ume.vector_store", None)
        if orig_pkg is not None:
            sys.modules["ume"] = orig_pkg
        else:
            sys.modules.pop("ume", None)


def test_add_dimension_mismatch(vector_store_cls):
    store = vector_store_cls(dim=2, use_gpu=False)

    with pytest.raises(ValueError):
        store.add("a", [1.0, 2.0, 3.0])


def test_query_invalid_input(vector_store_cls):
    store = vector_store_cls(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])
    with pytest.raises(ValueError):
        store.query("bad")  # type: ignore[arg-type]


def test_query_dimension_mismatch(vector_store_cls):
    store = vector_store_cls(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])
    with pytest.raises(ValueError):
        store.query([1.0])


def test_init_requires_faiss(monkeypatch, vector_store_cls):
    monkeypatch.setattr("ume.vector_store.faiss", None)
    with pytest.raises(ImportError):
        vector_store_cls(dim=2)


def test_query_records_metrics(vector_store_cls):
    store = vector_store_cls(dim=2, use_gpu=False)
    store.add("a", [0.0, 1.0])

    class DummyHist:
        def __init__(self) -> None:
            self.count = 0

        def observe(self, value: float) -> None:
            self.count += 1

    class DummyGauge:
        def __init__(self) -> None:
            self.value = 0

        def set(self, val: int) -> None:
            self.value = val

    h = DummyHist()
    g = DummyGauge()
    store.query_latency_metric = h
    store.index_size_metric = g

    result = store.query([0.0, 1.0])
    assert result == ["a"]
    assert h.count == 1
    assert g.value == 1


@pytest.mark.parametrize("k", [0, -1])
def test_query_invalid_k(vector_store_cls, k: int) -> None:
    store = vector_store_cls(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])

    with pytest.raises(ValueError):
        store.query([1.0, 0.0], k=k)


def test_query_respects_k(vector_store_cls) -> None:
    store = vector_store_cls(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])
    store.add("b", [0.0, 1.0])

    assert store.query([1.0, 0.0], k=1) == ["a"]
    res = store.query([1.0, 0.0], k=2)
    assert set(res) == {"a", "b"}


def test_gpu_resources_released_between_cycles(vector_store_cls):
    faiss = pytest.importorskip("faiss")
    if not hasattr(faiss, "StandardGpuResources") or faiss.get_num_gpus() == 0:
        pytest.skip("faiss compiled without GPU support")
    before = faiss.get_mem_usage_kb()
    for _ in range(3):
        store = vector_store_cls(dim=2, use_gpu=True, path=None)
        store.add("a", [1.0, 0.0])
        store.close()
    after = faiss.get_mem_usage_kb()
    assert after - before < 2048

