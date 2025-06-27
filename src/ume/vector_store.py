from __future__ import annotations

from typing import Any, Dict, List
from collections.abc import Iterable
from types import TracebackType
import numbers
import json
import logging
import os

import time
import threading

from .config import settings

import numpy as np

try:  # optional dependency
    import faiss
except Exception:  # pragma: no cover - optional dependency missing
    faiss = None

from ._internal.listeners import GraphListener
from .metrics import VECTOR_INDEX_SIZE, VECTOR_QUERY_LATENCY
from prometheus_client import Gauge, Histogram

logger = logging.getLogger(__name__)


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
        if faiss is None:
            raise ImportError("faiss is required for VectorStore")

        self.path = path or settings.UME_VECTOR_INDEX
        if path:  # pragma: no cover - filesystem
            dirpath = os.path.dirname(path)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)
        self.id_to_idx: Dict[str, int] = {}
        self.idx_to_id: List[str] = []
        self.vector_ts: Dict[str, int] = {}

        self.gpu_resources = None
        self.use_gpu = use_gpu if use_gpu is not None else settings.UME_VECTOR_USE_GPU
        self.dim = dim

        self.query_latency_metric = query_latency_metric
        self.index_size_metric = index_size_metric

        self._flush_interval = flush_interval
        self._flush_thread: threading.Thread | None = None
        self._flush_stop = threading.Event()
        self.lock = threading.Lock()

        self.index = faiss.IndexFlatL2(dim)
        if self.use_gpu:  # pragma: no cover - GPU code not exercised in tests
            try:
                self.gpu_resources = faiss.StandardGpuResources()
                self.gpu_resources.setTempMemory(
                    settings.UME_VECTOR_GPU_MEM_MB * 1024 * 1024
                )
                self.index = faiss.index_cpu_to_gpu(self.gpu_resources, 0, self.index)
            except AttributeError:
                # FAISS was compiled without GPU support
                pass

        if flush_interval is not None:  # pragma: no cover - requires threading
            self.start_background_flush(flush_interval)

    def __enter__(self) -> "VectorStore":  # pragma: no cover - simple passthrough
        """Return ``self`` to support use as a context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:  # pragma: no cover - context manager
        self.close()

    def __del__(self) -> None:  # pragma: no cover - destructor cleanup
        try:
            self.stop_background_flush()
        except Exception:
            logger.exception("Failed to stop background flush on delete")

    def start_background_flush(
        self, interval: float
    ) -> None:  # pragma: no cover - background thread
        """Periodically persist the index to disk in a background thread."""
        if self._flush_thread and self._flush_thread.is_alive():
            return

        def _loop() -> None:
            retries = 3
            while not self._flush_stop.wait(interval):
                for attempt in range(retries):
                    try:
                        self.save()
                        break
                    except Exception:  # pragma: no cover - log and continue
                        if attempt < retries - 1:
                            logger.warning(
                                "Background flush failed (attempt %s/%s), retrying",
                                attempt + 1,
                                retries,
                            )
                            time.sleep(0.1)
                        else:
                            logger.exception(
                                "Background flush failed after %s attempts",
                                retries,
                            )
                            break

        self._flush_stop.clear()
        self._flush_thread = threading.Thread(target=_loop, daemon=True)
        self._flush_thread.start()

    def stop_background_flush(self) -> None:  # pragma: no cover - background thread
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
        with self.lock:
            if item_id in self.id_to_idx:  # pragma: no cover - updating existing vector
                idx = self.id_to_idx[item_id]
                if hasattr(self.index, "vectors"):
                    self.index.vectors[idx] = arr[0]
                else:
                    try:
                        cpu_index = faiss.index_gpu_to_cpu(self.index)
                    except AttributeError:
                        cpu_index = self.index
                    vectors = [
                        cpu_index.reconstruct(i) for i in range(cpu_index.ntotal)
                    ]
                    vectors[idx] = arr[0]
                    new_index = faiss.IndexFlatL2(self.dim)
                    new_index.add(np.asarray(vectors))
                    cpu_index = new_index
                    if self.use_gpu and self.gpu_resources is not None:
                        self.index = faiss.index_cpu_to_gpu(
                            self.gpu_resources, 0, cpu_index
                        )
                    else:
                        self.index = cpu_index
            else:
                self.index.add(arr)
                self.id_to_idx[item_id] = len(self.idx_to_id)
                self.idx_to_id.append(item_id)
            self.vector_ts[item_id] = int(time.time())

        if persist and self.path:
            self.save(self.path)

    def delete(self, item_id: str) -> None:
        """Remove a vector from the store if present."""
        with self.lock:
            idx = self.id_to_idx.pop(item_id, None)
            if idx is None:
                self.vector_ts.pop(item_id, None)
                return
            del self.idx_to_id[idx]
            self.vector_ts.pop(item_id, None)
            self.id_to_idx = {v: i for i, v in enumerate(self.idx_to_id)}
            if hasattr(self.index, "vectors"):
                vectors = [self.index.vectors[i] for i in range(self.index.ntotal) if i != idx]
                self.index = faiss.IndexFlatL2(self.dim)
                if vectors:
                    self.index.add(np.asarray(vectors))
            else:
                try:
                    cpu_index = faiss.index_gpu_to_cpu(self.index)
                except AttributeError:
                    cpu_index = self.index
                vectors = [cpu_index.reconstruct(i) for i in range(cpu_index.ntotal) if i != idx]
                new_index = faiss.IndexFlatL2(self.dim)
                if vectors:
                    new_index.add(np.asarray(vectors))
                cpu_index = new_index
                if self.use_gpu and self.gpu_resources is not None:
                    self.index = faiss.index_cpu_to_gpu(self.gpu_resources, 0, cpu_index)
                else:
                    self.index = cpu_index

    def expire_vectors(self, max_age_seconds: int) -> None:
        """Delete vectors older than ``max_age_seconds``."""
        cutoff = int(time.time()) - max_age_seconds
        expired = [vid for vid, ts in self.vector_ts.items() if ts < cutoff]
        for vid in expired:
            self.delete(vid)

    def save(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        """Persist the FAISS index and metadata to ``path``."""
        path = path or self.path
        if path is None:
            return
        with self.lock:
            if self.use_gpu and self.gpu_resources is not None:
                cpu_index = faiss.index_gpu_to_cpu(self.index)
            else:
                cpu_index = self.index
            faiss.write_index(cpu_index, path)
            with open(path + ".json", "w", encoding="utf-8") as f:
                json.dump({"ids": self.idx_to_id, "ts": self.vector_ts}, f)


    def load(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        """Load a FAISS index and metadata from ``path``."""
        path = path or self.path
        if path is None:
            return
        with self.lock:
            self.index = faiss.read_index(path)
            try:
                with open(path + ".json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.idx_to_id = data
                        self.vector_ts = {i: int(time.time()) for i in data}
                    else:
                        self.idx_to_id = data.get("ids", [])
                        self.vector_ts = {k: int(v) for k, v in data.get("ts", {}).items()}
            except FileNotFoundError:
                self.idx_to_id = []
                self.vector_ts = {}

            self.id_to_idx = {v: i for i, v in enumerate(self.idx_to_id)}
            self.dim = self.index.d
            if self.use_gpu:
                try:
                    self.gpu_resources = faiss.StandardGpuResources()
                    self.index = faiss.index_cpu_to_gpu(
                        self.gpu_resources, 0, self.index
                    )
                except AttributeError:
                    pass

    def close(self) -> None:  # pragma: no cover - filesystem
        """Stop background flush and persist index to disk."""
        self.stop_background_flush()
        if self.path:
            self.save(self.path)

    def query(self, vector: List[float], k: int = 5) -> List[str]:
        start = time.perf_counter()
        try:
            if not self.idx_to_id:
                return []
            if (
                not isinstance(vector, Iterable)
                or isinstance(vector, (str, bytes))
                or not all(isinstance(v, numbers.Real) for v in vector)
            ):
                raise ValueError("vector must be an iterable of numbers")
            arr = np.asarray(vector, dtype="float32").reshape(1, -1)
            if arr.shape[1] != self.dim:
                raise ValueError(
                    f"Expected vector of dimension {self.dim}, got {arr.shape[1]}"
                )
            with self.lock:
                _, indices = self.index.search(arr, min(k, len(self.idx_to_id)))
                return [self.idx_to_id[i] for i in indices[0] if i != -1]
        finally:
            if self.query_latency_metric is not None:
                self.query_latency_metric.observe(time.perf_counter() - start)
            if self.index_size_metric is not None:
                self.index_size_metric.set(len(self.idx_to_id))

    def get_vector_timestamps(self) -> Dict[str, int]:
        """Return mapping of item IDs to their last update timestamp."""
        with self.lock:
            return dict(self.vector_ts)


class VectorStoreListener(GraphListener):
    """GraphListener that indexes embeddings from node attributes."""

    def __init__(self, store: VectorStore) -> None:
        self.store = store

    def on_node_created(
        self, node_id: str, attributes: Dict[str, Any]
    ) -> None:  # pragma: no cover - simple passthrough
        emb = attributes.get("embedding")
        if isinstance(emb, list):
            self.store.add(node_id, emb)

    def on_node_updated(
        self, node_id: str, attributes: Dict[str, Any]
    ) -> None:  # pragma: no cover - simple passthrough
        emb = attributes.get("embedding")
        if isinstance(emb, list):
            self.store.add(node_id, emb)

    def on_edge_created(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:  # pragma: no cover - unused hooks
        pass

    def on_edge_deleted(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:  # pragma: no cover - unused hooks
        pass


def create_default_store() -> VectorStore:  # pragma: no cover - trivial wrapper
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

# Ensure ``ume.vector_store`` is set when imported standalone
if __name__ == "ume.vector_store":
    import sys as _sys
    parent = _sys.modules.get("ume")
    if parent is not None and not hasattr(parent, "vector_store"):
        parent.vector_store = _sys.modules[__name__]  # type: ignore[attr-defined]
