import types
import importlib.metadata as metadata
import importlib

from ume.vector_backends import get_backend, available_backends, load_entrypoints
from ume.vector_store import VectorBackend


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

    ep = metadata.EntryPoint(name="dummy", value="dummy_mod:DummyBackend", group="ume.vector_backends")
    monkeypatch.setattr(metadata, "entry_points", lambda group=None: (ep,) if group == "ume.vector_backends" else ())

    load_entrypoints()

    assert "dummy" in available_backends()
    assert get_backend("dummy") is DummyBackend
