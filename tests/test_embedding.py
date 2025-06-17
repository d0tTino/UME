import importlib
import sys
import types

from typing import List

class DummyModel:
    def __init__(self, dim: int) -> None:
        self.dim = dim

    def encode(self, text: str):  # pragma: no cover - simple stub
        import numpy as np
        return np.zeros(self.dim, dtype=float)


def test_generate_embedding(monkeypatch):
    dummy_module = types.SimpleNamespace(SentenceTransformer=lambda name: DummyModel(5))
    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy_module)
    import ume.embedding as emb
    importlib.reload(emb)
    vec = emb.generate_embedding("hello")
    assert vec == [0.0] * 5
