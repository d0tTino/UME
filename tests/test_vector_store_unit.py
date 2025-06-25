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
