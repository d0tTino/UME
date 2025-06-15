from __future__ import annotations

from typing import List, Dict, Any

import numpy as np
import faiss

from ._internal.listeners import GraphListener


class VectorStore:
    """Simple FAISS-based vector store."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.index = faiss.IndexFlatL2(dim)
        self.id_to_idx: Dict[str, int] = {}
        self.idx_to_id: List[str] = []

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
