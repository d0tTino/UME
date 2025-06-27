# ruff: noqa: E402
import pytest
from pathlib import Path

faiss = pytest.importorskip("faiss")
if not hasattr(faiss, "IndexFlatL2"):
    pytest.skip("faiss is missing required functionality", allow_module_level=True)

import importlib.util
import sys
import types
from typing import Any, Type

root = Path(__file__).resolve().parents[1]
VectorStore: Type[Any]


@pytest.fixture(scope="module", autouse=True)
def vector_store_module():
    orig_ume = sys.modules.get("ume")
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
    package.vector_store = module  # type: ignore[attr-defined]
    global VectorStore
    VectorStore = module.VectorStore

    yield

    if orig_ume is not None:
        sys.modules["ume"] = orig_ume
    else:
        sys.modules.pop("ume", None)

    if orig_vs is not None:
        sys.modules["ume.vector_store"] = orig_vs
    else:
        sys.modules.pop("ume.vector_store", None)


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