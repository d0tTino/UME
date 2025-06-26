# ruff: noqa: E402
import pytest

faiss = pytest.importorskip("faiss")
if not hasattr(faiss, "IndexFlatL2"):
    pytest.skip("faiss is missing required functionality", allow_module_level=True)

from ume.vector_store import VectorStore


def test_add_dimension_mismatch():
    store = VectorStore(dim=2, use_gpu=False)
    with pytest.raises(ValueError):
        store.add("a", [1.0, 2.0, 3.0])


def test_query_invalid_input():
    store = VectorStore(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])
    with pytest.raises(ValueError):
        store.query("bad")  # type: ignore[arg-type]


def test_query_dimension_mismatch():
    store = VectorStore(dim=2, use_gpu=False)
    store.add("a", [1.0, 0.0])
    with pytest.raises(ValueError):
        store.query([1.0])


def test_init_requires_faiss(monkeypatch):
    monkeypatch.setattr("ume.vector_store.faiss", None)
    with pytest.raises(ImportError):
        VectorStore(dim=2)


def test_query_records_metrics():
    store = VectorStore(dim=2, use_gpu=False)
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
