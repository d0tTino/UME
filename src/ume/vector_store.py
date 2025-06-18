from __future__ import annotations

from typing import Any, Dict, List
import json

import time
import threading

from .config import settings

import numpy as np
import faiss

from ._internal.listeners import GraphListener
from .metrics import VECTOR_INDEX_SIZE, VECTOR_QUERY_LATENCY
from prometheus_client import Gauge, Histogram


class VectorStore:
    """Simple FAISS-based vector store with optional persistence."""

    def __init__(
        self,
        dim: int,
        *,
        use_gpu: bool | None = None,
        path: str | None = None,
        flush_interval: float | None = None,
        query_latency_metric: Histogram | None = None,
        index_size_metric: Gauge | None = None,

    ) -> None:
        self.path = path or settings.UME_VECTOR_INDEX
        self.id_to_idx: Dict[str, int] = {}
        self.idx_to_id: List[str] = []
        self.gpu_resources = None
        self.use_gpu = use_gpu if use_gpu is not None else settings.UME_VECTOR_USE_GPU
        self.dim = dim

        self.query_latency_metric = query_latency_metric
        self.index_size_metric = index_size_metric

        self._flush_interval = flush_interval
        self._flush_thread: threading.Thread | None = None
        self._flush_stop = threading.Event()


        self.index = faiss.IndexFlatL2(dim)
        if self.use_gpu:
            try:
                self.gpu_resources = faiss.StandardGpuResources()
                self.gpu_resources.setTempMemory(
                    settings.UME_VECTOR_GPU_MEM_MB * 1024 * 1024
                )
                self.index = faiss.index_cpu_to_gpu(self.gpu_resources, 0, self.index)
            except AttributeError:
                # FAISS was compiled without GPU support
                pass

        if flush_interval is not None:
            self.start_background_flush(flush_interval)

    def start_background_flush(self, interval: float) -> None:
        """Periodically persist the index to disk in a background thread."""
        if self._flush_thread and self._flush_thread.is_alive():
            return

        def _loop() -> None:
            while not self._flush_stop.wait(interval):
                self.save()

        self._flush_stop.clear()
        self._flush_thread = threading.Thread(target=_loop, daemon=True)
        self._flush_thread.start()


    def stop_background_flush(self) -> None:
        """Stop the background flush thread if running."""
        if self._flush_thread:
            self._flush_stop.set()
            self._flush_thread.join()
            self._flush_thread = None

    def add(self, item_id: str, vector: List[float], *, persist: bool = False) -> None:
        arr = np.asarray(vector, dtype="float32").reshape(1, -1)
        if arr.shape[1] != self.dim:
            raise ValueError(
                f"Expected vector of dimension {self.dim}, got {arr.shape[1]}"
            )
        self.index.add(arr)
        self.id_to_idx[item_id] = len(self.idx_to_id)
        self.idx_to_id.append(item_id)
        if persist and self.path:
            self.save(self.path)

    def save(self, path: str | None = None) -> None:
        """Persist the FAISS index and metadata to ``path``."""
        path = path or self.path
        if path is None:
            return
        if self.use_gpu and self.gpu_resources is not None:
            cpu_index = faiss.index_gpu_to_cpu(self.index)
        else:
            cpu_index = self.index
        faiss.write_index(cpu_index, path)
        with open(path + ".json", "w", encoding="utf-8") as f:
            json.dump(self.idx_to_id, f)

    def load(self, path: str | None = None) -> None:
        """Load a FAISS index and metadata from ``path``."""
        path = path or self.path
        if path is None:
            return
        self.index = faiss.read_index(path)
        try:
            with open(path + ".json", "r", encoding="utf-8") as f:
                self.idx_to_id = json.load(f)
        except FileNotFoundError:
            self.idx_to_id = []
        self.id_to_idx = {v: i for i, v in enumerate(self.idx_to_id)}
        self.dim = self.index.d
        if self.use_gpu:
            try:
                self.gpu_resources = faiss.StandardGpuResources()
                self.index = faiss.index_cpu_to_gpu(self.gpu_resources, 0, self.index)
            except AttributeError:
                pass

    def close(self) -> None:
        """Stop background flush and persist index to disk."""
        self.stop_background_flush()
        if self.path:
            self.save(self.path)

    def query(self, vector: List[float], k: int = 5) -> List[str]:
        start = time.perf_counter()
        try:
            if not self.idx_to_id:
                return []
            arr = np.asarray(vector, dtype="float32").reshape(1, -1)
            if arr.shape[1] != self.dim:
                raise ValueError(
                    f"Expected vector of dimension {self.dim}, got {arr.shape[1]}"
                )
            _, indices = self.index.search(arr, min(k, len(self.idx_to_id)))
            return [self.idx_to_id[i] for i in indices[0] if i != -1]
        finally:
            if self.query_latency_metric is not None:
                self.query_latency_metric.observe(time.perf_counter() - start)
            if self.index_size_metric is not None:
                self.index_size_metric.set(len(self.idx_to_id))


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

    def on_edge_created(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:
        pass

    def on_edge_deleted(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:
        pass


def create_default_store() -> VectorStore:
    """Instantiate a :class:`VectorStore` using ``ume.config.settings``."""
    return VectorStore(
        dim=settings.UME_VECTOR_DIM,
        use_gpu=settings.UME_VECTOR_USE_GPU,
        path=settings.UME_VECTOR_INDEX,
        query_latency_metric=VECTOR_QUERY_LATENCY,
        index_size_metric=VECTOR_INDEX_SIZE,
    )

# For backward compatibility ---------------------------------------------------

# ``create_vector_store`` used to be exported. Provide an alias so older imports
# continue to work without modification.
create_vector_store = create_default_store
