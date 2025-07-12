
"""Example vector backend plugin."""

from typing import Dict

import numpy as np

from ume.vector_backends import register_backend
from ume.vector_store import VectorBackend


class MemoryBackend(VectorBackend):
    """Naive in-memory backend demonstrating the plugin API."""

    def __init__(self, dim: int, **_: object) -> None:
        self.dim = dim
        self.vectors: Dict[str, list[float]] = {}

    def add(self, item_id: str, vector: list[float], *, persist: bool = False) -> None:
        self.vectors[item_id] = list(vector)

    def add_many(self, vectors: Dict[str, list[float]], *, persist: bool = False) -> None:
        for vid, vec in vectors.items():
            self.add(vid, vec)

    def delete(self, item_id: str) -> None:
        self.vectors.pop(item_id, None)

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        if not self.vectors:
            return []
        arr = np.asarray([self.vectors[i] for i in self.vectors], dtype="float32")
        q = np.asarray(vector, dtype="float32")
        dists = np.linalg.norm(arr - q, axis=1)
        ids = list(self.vectors)
        idxs = np.argsort(dists)[:k]
        return [ids[i] for i in idxs]

    def save(self, path: str | None = None) -> None:
        pass

    def load(self, path: str | None = None) -> None:
        pass

    def close(self) -> None:
        pass

    def get_vector_timestamps(self) -> Dict[str, int]:
        return {k: 0 for k in self.vectors}


register_backend("memory", MemoryBackend)
