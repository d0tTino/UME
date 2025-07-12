from __future__ import annotations

from typing import Dict, Iterable
from types import TracebackType
import json
import logging
import os
import numbers
import time
import threading
from importlib import metadata

import numpy as np

from ..config import settings
from prometheus_client import Gauge, Histogram

from ..vector_store import VectorBackend

try:  # optional dependency
    import faiss
except Exception:  # pragma: no cover - optional dependency missing
    faiss = None

logger = logging.getLogger(__name__)

_BACKENDS: Dict[str, type[VectorBackend]] = {}

def register_backend(name: str, cls: type[VectorBackend]) -> None:
    """Register a vector backend class under ``name``."""
    _BACKENDS[name.lower()] = cls

def get_backend(name: str) -> type[VectorBackend]:
    """Return the backend class registered under ``name``."""
    key = name.lower()
    if key not in _BACKENDS:
        raise ValueError(f"Unknown vector backend: {name}")
    return _BACKENDS[key]

def available_backends() -> Iterable[str]:
    """Return names of all registered backends."""
    return list(_BACKENDS.keys())


ENTRYPOINT_GROUP = "ume.vector_backends"


def load_entrypoints() -> None:
    """Load and register backends from ``ENTRYPOINT_GROUP`` entry points."""
    try:
        eps = metadata.entry_points(group=ENTRYPOINT_GROUP)
    except Exception:
        return
    for ep in eps:
        try:
            cls = ep.load()
        except Exception:  # pragma: no cover - import failures
            logger.exception("Failed to load vector backend %s", ep.value)
            continue
        register_backend(ep.name, cls)


class FaissBackend(VectorBackend):
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
        if faiss is None:
            raise ImportError("faiss is required for FaissBackend")

        self.path = path or settings.UME_VECTOR_INDEX
        if path:  # pragma: no cover - filesystem
            dirpath = os.path.dirname(path)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)
        self.id_to_idx: Dict[str, int] = {}
        self.idx_to_id: list[str] = []
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
        if self._flush_thread:
            self._flush_stop.set()
            self._flush_thread.join()
            self._flush_thread = None

    def add(self, item_id: str, vector: list[float], *, persist: bool = False) -> None:
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

    def add_many(self, vectors: Dict[str, list[float]], *, persist: bool = False) -> None:
        if not vectors:
            return

        ids = []
        arr_list = []
        updates: list[tuple[str, list[float]]] = []

        for vid, vec in vectors.items():
            if vid in self.id_to_idx:
                updates.append((vid, vec))
            else:
                ids.append(vid)
                arr_list.append(vec)

        for vid, vec in updates:
            self.add(vid, vec)

        if arr_list:
            arr = np.asarray(arr_list, dtype="float32")
            if arr.shape[1] != self.dim:
                raise ValueError(
                    f"Expected vector of dimension {self.dim}, got {arr.shape[1]}"
                )
            with self.lock:
                self.index.add(arr)
                for vid in ids:
                    self.id_to_idx[vid] = len(self.idx_to_id)
                    self.idx_to_id.append(vid)
                    self.vector_ts[vid] = int(time.time())

        if persist and self.path:
            self.save(self.path)

    def delete(self, item_id: str) -> None:
        with self.lock:
            idx = self.id_to_idx.pop(item_id, None)
            if idx is None:
                self.vector_ts.pop(item_id, None)
                return
            self.idx_to_id.pop(idx)
            self.vector_ts.pop(item_id, None)
            ids = list(self.id_to_idx.keys())
            self.id_to_idx = {id_: i for i, id_ in enumerate(ids)}
            vectors = [self.index.reconstruct(i) for i in range(self.index.ntotal)]
            vectors.pop(idx)
            self.index = faiss.IndexFlatL2(self.dim)
            if vectors:
                self.index.add(np.asarray(vectors))

    def query(self, vector: list[float], k: int = 5) -> list[str]:
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

    def save(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        path = path or self.path
        if not path:
            raise ValueError("No path specified for saving index")
        with self.lock:
            if self.gpu_resources:
                index = faiss.index_gpu_to_cpu(self.index)
            else:
                index = self.index
            faiss.write_index(index, path)
            with open(f"{path}.json", "w", encoding="utf-8") as f:
                json.dump({"ids": self.idx_to_id, "ts": self.vector_ts}, f)

    def load(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        path = path or self.path
        if not path:
            raise ValueError("No path specified for loading index")
        with self.lock:
            index = faiss.read_index(path)
            if self.use_gpu and self.gpu_resources is not None:
                index = faiss.index_cpu_to_gpu(self.gpu_resources, 0, index)
            self.index = index
            with open(f"{path}.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.idx_to_id = data.get("ids", [])
                self.vector_ts = {k: int(v) for k, v in data.get("ts", {}).items()}
                self.id_to_idx = {v: i for i, v in enumerate(self.idx_to_id)}
                if index.ntotal:
                    self.dim = index.d

    def close(self) -> None:  # pragma: no cover - filesystem
        self.stop_background_flush()
        if self.path:
            self.save(self.path)
        if self.gpu_resources is not None:
            del self.gpu_resources
            self.gpu_resources = None

    def get_vector_timestamps(self) -> Dict[str, int]:
        """Return mapping of item IDs to their last update timestamp."""
        with self.lock:
            return dict(self.vector_ts)

    def expire_vectors(self, max_age_seconds: int) -> None:
        cutoff = int(time.time()) - max_age_seconds
        with self.lock:
            to_delete = [k for k, ts in self.vector_ts.items() if ts < cutoff]
        for vid in to_delete:
            self.delete(vid)


class ChromaBackend(VectorBackend):
    """Minimal in-memory backend used for testing the backend interface."""

    def __init__(
        self,
        dim: int,
        *,
        path: str | None = None,
        flush_interval: float | None = None,
        query_latency_metric: Histogram | None = None,
        index_size_metric: Gauge | None = None,
        **__: object,
    ) -> None:
        self.path = path or settings.UME_VECTOR_INDEX
        if path:  # pragma: no cover - filesystem
            dirpath = os.path.dirname(path)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)
        self.dim = dim
        self.vectors: list[np.ndarray] = []
        self.id_to_idx: dict[str, int] = {}
        self.idx_to_id: list[str] = []
        self.vector_ts: dict[str, int] = {}

        self.query_latency_metric = query_latency_metric
        self.index_size_metric = index_size_metric

        self._flush_interval = flush_interval
        self._flush_thread: threading.Thread | None = None
        self._flush_stop = threading.Event()
        self.lock = threading.Lock()

        if flush_interval is not None:  # pragma: no cover - requires threading
            self.start_background_flush(flush_interval)

    def __del__(self) -> None:  # pragma: no cover - destructor cleanup
        try:
            self.close()
        except Exception:  # pragma: no cover - log and swallow errors
            logger.exception("Failed to close ChromaBackend on delete")

    def start_background_flush(self, interval: float) -> None:  # pragma: no cover - background thread
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
        if self._flush_thread:
            self._flush_stop.set()
            self._flush_thread.join()
            self._flush_thread = None

    def add(self, item_id: str, vector: list[float], *, persist: bool = False) -> None:
        arr = np.asarray(vector, dtype="float32").reshape(1, -1)
        if arr.shape[1] != self.dim:
            raise ValueError(
                f"Expected vector of dimension {self.dim}, got {arr.shape[1]}"
            )
        with self.lock:
            if item_id in self.id_to_idx:
                idx = self.id_to_idx[item_id]
                self.vectors[idx] = arr[0]
            else:
                self.id_to_idx[item_id] = len(self.idx_to_id)
                self.idx_to_id.append(item_id)
                self.vectors.append(arr[0])
            self.vector_ts[item_id] = int(time.time())
        if persist and self.path:
            self.save(self.path)

    def add_many(self, vectors: Dict[str, list[float]], *, persist: bool = False) -> None:
        if not vectors:
            return
        for vid, vec in vectors.items():
            self.add(vid, vec)
        if persist and self.path:
            self.save(self.path)

    def delete(self, item_id: str) -> None:
        with self.lock:
            idx = self.id_to_idx.pop(item_id, None)
            if idx is None:
                self.vector_ts.pop(item_id, None)
                return
            self.idx_to_id.pop(idx)
            self.vector_ts.pop(item_id, None)
            self.vectors.pop(idx)
            ids = list(self.id_to_idx.keys())
            self.id_to_idx = {id_: i for i, id_ in enumerate(ids)}

    def query(self, vector: list[float], k: int = 5) -> list[str]:
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
                mat = np.asarray(self.vectors, dtype="float32")
                dists = np.linalg.norm(mat - arr, axis=1)
                idxs = np.argsort(dists)[: min(k, len(self.idx_to_id))]
                return [self.idx_to_id[i] for i in idxs]
        finally:
            if self.query_latency_metric is not None:
                self.query_latency_metric.observe(time.perf_counter() - start)
            if self.index_size_metric is not None:
                self.index_size_metric.set(len(self.idx_to_id))

    def save(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        path = path or self.path
        if not path:
            raise ValueError("No path specified for saving index")
        with self.lock:
            arr = np.asarray(self.vectors, dtype="float32")
            with open(path, "wb") as f:
                np.save(f, arr)
            with open(f"{path}.json", "w", encoding="utf-8") as f:
                json.dump({"ids": self.idx_to_id, "ts": self.vector_ts}, f)

    def load(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        path = path or self.path
        if not path:
            raise ValueError("No path specified for loading index")
        with self.lock:
            arr = np.array([])
            try:
                with open(path, "rb") as f:
                    arr = np.load(f)
                self.vectors = list(np.asarray(arr, dtype="float32"))
                with open(f"{path}.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.idx_to_id = data.get("ids", [])
                    self.vector_ts = {k: int(v) for k, v in data.get("ts", {}).items()}
            except FileNotFoundError:
                self.idx_to_id = []
                self.vector_ts = {}
            self.id_to_idx = {v: i for i, v in enumerate(self.idx_to_id)}
            if arr.size:
                self.dim = arr.shape[1]

    def close(self) -> None:  # pragma: no cover - filesystem
        self.stop_background_flush()
        if self.path:
            self.save(self.path)

    def get_vector_timestamps(self) -> Dict[str, int]:
        with self.lock:
            return dict(self.vector_ts)


register_backend("faiss", FaissBackend)
register_backend("chroma", ChromaBackend)

# Load any third-party backends exposed via entry points
try:  # pragma: no cover - import side effects
    load_entrypoints()
except Exception:  # pragma: no cover - log but proceed
    logger.exception("Failed to load vector backend entry points")
