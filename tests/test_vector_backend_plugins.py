import types
import importlib
from types import SimpleNamespace

from ume.vector_backends import get_backend, available_backends, load_entrypoints
from ume.vector_store import VectorBackend
from ume.plugins.registry import clear_plugins


class DummyBackend(VectorBackend):
    def add(self, item_id: str, vector: list[float], *, persist: bool = False) -> None:
        pass

    def add_many(self, vectors: dict[str, list[float]], *, persist: bool = False) -> None:
        pass

    def delete(self, item_id: str) -> None:
        pass

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        return []

    def save(self, path: str | None = None) -> None:
        pass

    def load(self, path: str | None = None) -> None:
        pass

    def close(self) -> None:
        pass

    def get_vector_timestamps(self) -> dict[str, int]:
        return {}


def test_entrypoint_registration(monkeypatch):
    module = types.ModuleType("dummy_mod")
    module.DummyBackend = DummyBackend
    monkeypatch.setitem(importlib.sys.modules, "dummy_mod", module)

    ep = SimpleNamespace(name="dummy", load=lambda: DummyBackend)
    monkeypatch.setattr(
        "ume.plugins.registry.entry_points",
        lambda group=None: (ep,) if group == "ume.vector_backends" else (),
    )

    clear_plugins(capability="vector_backend")

    load_entrypoints()

    assert "dummy" in available_backends()
    assert get_backend("dummy") is DummyBackend


def test_backend_loaded_on_import(monkeypatch):
    module = types.ModuleType("dummy_mod")
    module.DummyBackend = DummyBackend
    monkeypatch.setitem(importlib.sys.modules, "dummy_mod", module)

    ep = SimpleNamespace(name="dummy_imp", load=lambda: DummyBackend)
    monkeypatch.setattr(
        "ume.plugins.registry.entry_points",
        lambda group=None: (ep,) if group == "ume.vector_backends" else (),
    )

    import sys

    sys.modules.pop("ume.vector_backends", None)
    reloaded = importlib.import_module("ume.vector_backends")

    assert "dummy_imp" in reloaded.available_backends()
    assert reloaded.get_backend("dummy_imp") is DummyBackend
