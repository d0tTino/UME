from __future__ import annotations

import json
import logging
import numbers
import os
import threading
import time
from collections.abc import Iterable
from types import TracebackType
from typing import Dict, List

import numpy as np

from ..config import settings
from .base import VectorStore
from prometheus_client import Gauge, Histogram

try:  # optional dependency
    import faiss
except Exception:  # pragma: no cover - optional dependency missing
    faiss = None

logger = logging.getLogger(__name__)


class FaissBackend(VectorStore):
    """FAISS-based vector store with optional persistence."""

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
        from .. import vector_store as vs

        lib = vs.faiss
        if lib is None:
            raise ImportError("faiss is required for FaissBackend")
        global faiss
        faiss = lib

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

    def __enter__(self) -> "FaissBackend":  # pragma: no cover - simple passthrough
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
            self.close()
        except Exception:  # pragma: no cover - log and swallow errors
            logger.exception("Failed to close FaissBackend on delete")

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
                    if self.use_gpu and self.gpu_resources is not None:
                        self.index = faiss.index_cpu_to_gpu(
                            self.gpu_resources, 0, new_index
                        )
                    else:
                        self.index = new_index
            else:
                self.id_to_idx[item_id] = len(self.idx_to_id)
                self.idx_to_id.append(item_id)
                self.index.add(arr)
            self.vector_ts[item_id] = int(time.time())
        if persist and self.path:
            self.save(self.path)

    def add_many(self, vectors: Dict[str, List[float]], *, persist: bool = False) -> None:
        if not vectors:
            return
        arr = np.asarray(list(vectors.values()), dtype="float32").reshape(len(vectors), -1)
        if arr.shape[1] != self.dim:
            raise ValueError(
                f"Expected vectors of dimension {self.dim}, got {arr.shape[1]}"
            )
        with self.lock:
            self.index.add(arr)
            self.idx_to_id.extend(vectors.keys())
            self.id_to_idx.update({vid: i for i, vid in enumerate(self.idx_to_id)})
            for vid in vectors:
                self.vector_ts[vid] = int(time.time())
        if persist and self.path:
            self.save(self.path)

    def delete(self, item_id: str) -> None:
        with self.lock:
            idx = self.id_to_idx.pop(item_id, None)
            if idx is None:
                self.vector_ts.pop(item_id, None)
                return
            del self.idx_to_id[idx]
            self.index.remove_ids(np.array([idx], dtype="int64"))
            self.vector_ts.pop(item_id, None)
            self.id_to_idx = {v: i for i, v in enumerate(self.idx_to_id)}

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
        """Stop background flush, persist index, and release GPU memory."""
        self.stop_background_flush()
        if self.path:
            self.save(self.path)
        if self.use_gpu and self.gpu_resources is not None:
            try:
                gpu_index = (
                    faiss.downcast_index(self.index)
                    if hasattr(faiss, "downcast_index")
                    else self.index
                )
                self.index = faiss.index_gpu_to_cpu(gpu_index)
            except AttributeError:
                # FAISS built without GPU support
                pass
            self.gpu_resources = None

    def query(self, vector: List[float], k: int = 5) -> List[str]:
        start = time.perf_counter()
        try:
            if not self.idx_to_id:
                return []
            if k <= 0:
                raise ValueError("k must be a positive integer")
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
