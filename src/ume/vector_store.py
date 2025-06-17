from __future__ import annotations

from typing import List, Dict, Any

from .config import settings

import numpy as np
import faiss

from ._internal.listeners import GraphListener


class VectorStore:
    """Simple FAISS-based vector store."""

    def __init__(self, dim: int, *, use_gpu: bool | None = None) -> None:
        self.dim = dim
        self.id_to_idx: Dict[str, int] = {}
        self.idx_to_id: List[str] = []
        self.gpu_resources = None

        # Allow env var ``UME_VECTOR_USE_GPU`` to control GPU usage when
        # ``use_gpu`` is not explicitly provided.
        if use_gpu is None:
            use_gpu = settings.UME_VECTOR_USE_GPU

        self.index = faiss.IndexFlatL2(dim)
        if use_gpu:
            try:
                self.gpu_resources = faiss.StandardGpuResources()
                self.index = faiss.index_cpu_to_gpu(self.gpu_resources, 0, self.index)
            except AttributeError:
                # FAISS was compiled without GPU support
                pass

    def add(self, item_id: str, vector: List[float]) -> None:
        arr = np.asarray(vector, dtype="float32").reshape(1, -1)
        if arr.shape[1] != self.dim:
            raise ValueError(f"Expected vector of dimension {self.dim}, got {arr.shape[1]}")
        self.index.add(arr)
        self.id_to_idx[item_id] = len(self.idx_to_id)
        self.idx_to_id.append(item_id)

    def query(self, vector: List[float], k: int = 5) -> List[str]:
        if not self.idx_to_id:
            return []
        arr = np.asarray(vector, dtype="float32").reshape(1, -1)
        if arr.shape[1] != self.dim:
            raise ValueError(f"Expected vector of dimension {self.dim}, got {arr.shape[1]}")
        _, indices = self.index.search(arr, min(k, len(self.idx_to_id)))
        return [self.idx_to_id[i] for i in indices[0] if i != -1]

    def save(self, path: str) -> None:
        """Persist the FAISS index and id mapping to ``path``."""
        index = self.index
        # ``write_index`` only operates on CPU indexes.
        if self.gpu_resources is not None:
            index = faiss.index_gpu_to_cpu(index)
        faiss.write_index(index, path)
        with open(f"{path}.json", "w", encoding="utf-8") as f:
            import json

            json.dump(self.idx_to_id, f)

    @classmethod
    def load(cls, path: str, *, use_gpu: bool | None = None) -> "VectorStore":
        """Load a previously saved index from ``path``."""
        index = faiss.read_index(path)
        dim = index.d
        store = cls(dim=dim, use_gpu=use_gpu)
        if store.gpu_resources is not None:
            index = faiss.index_cpu_to_gpu(store.gpu_resources, 0, index)
        store.index = index
        with open(f"{path}.json", "r", encoding="utf-8") as f:
            import json

            store.idx_to_id = json.load(f)
        store.id_to_idx = {item_id: i for i, item_id in enumerate(store.idx_to_id)}
        return store


class VectorStoreListener(GraphListener):
    """GraphListener that indexes embeddings from node attributes."""

    def __init__(self, store: VectorStore) -> None:
        self.store = store

    def on_node_created(self, node_id: str, attributes: Dict[str, Any]) -> None:
        emb = attributes.get("embedding")
        if isinstance(emb, list):
            self.store.add(node_id, emb)

    def on_node_updated(self, node_id: str, attributes: Dict[str, Any]) -> None:
        emb = attributes.get("embedding")
        if isinstance(emb, list):
            self.store.add(node_id, emb)

    def on_edge_created(self, source_node_id: str, target_node_id: str, label: str) -> None:
        pass

    def on_edge_deleted(self, source_node_id: str, target_node_id: str, label: str) -> None:
        pass


def create_default_store() -> VectorStore:
    """Instantiate a :class:`VectorStore` using ``ume.config.settings``."""
    return VectorStore(
        dim=settings.UME_VECTOR_DIM,
        use_gpu=settings.UME_VECTOR_USE_GPU,
    )
