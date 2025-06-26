# ruff: noqa: E402
import pytest
import time
from pathlib import Path

faiss = pytest.importorskip("faiss")
if not hasattr(faiss, "IndexFlatL2"):
    pytest.skip("faiss is missing required functionality", allow_module_level=True)

import importlib.util
import sys
import types

root = Path(__file__).resolve().parents[1]
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
VectorStore = module.VectorStore


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


def test_del_stops_flush_thread(tmp_path: Path) -> None:
    path = tmp_path / "del.faiss"
    store = VectorStore(dim=2, use_gpu=False, path=str(path), flush_interval=0.05)
    store.add("x", [1.0, 0.0])
    thread = store._flush_thread
    assert thread is not None and thread.is_alive()
    store.__del__()
    time.sleep(0.1)
    assert thread is not None and not thread.is_alive()
