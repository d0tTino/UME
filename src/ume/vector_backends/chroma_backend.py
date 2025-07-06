from __future__ import annotations

import json
import logging
import numbers
import os
import threading
import time
from collections.abc import Iterable
from typing import Dict, List

import numpy as np

from ..config import settings
from .base import VectorStore
from prometheus_client import Gauge, Histogram

logger = logging.getLogger(__name__)


class ChromaBackend(VectorStore):
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

    def add(self, item_id: str, vector: List[float], *, persist: bool = False) -> None:
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

    def add_many(self, vectors: Dict[str, List[float]], *, persist: bool = False) -> None:
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
            del self.idx_to_id[idx]
            del self.vectors[idx]
            self.vector_ts.pop(item_id, None)
            self.id_to_idx = {v: i for i, v in enumerate(self.idx_to_id)}

    def expire_vectors(self, max_age_seconds: int) -> None:
        cutoff = int(time.time()) - max_age_seconds
        expired = [vid for vid, ts in self.vector_ts.items() if ts < cutoff]
        for vid in expired:
            self.delete(vid)

    def save(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        path = path or self.path
        if path is None:
            return
        with self.lock:
            arr = np.asarray(self.vectors, dtype="float32") if self.vectors else np.empty((0, self.dim), dtype="float32")
            with open(path, "wb") as f:
                np.save(f, arr)
            with open(path + ".json", "w", encoding="utf-8") as f:
                json.dump({"ids": self.idx_to_id, "ts": self.vector_ts}, f)

    def load(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        path = path or self.path
        if path is None:
            return
        with self.lock:
            try:
                with open(path, "rb") as f:
                    arr = np.load(f)
            except FileNotFoundError:
                self.vectors = []
                self.idx_to_id = []
                self.id_to_idx = {}
                self.vector_ts = {}
                return
            self.vectors = [v for v in arr]
            try:
                with open(path + ".json", "r", encoding="utf-8") as f:
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
                mat = np.asarray(self.vectors, dtype="float32")
                dists = np.linalg.norm(mat - arr, axis=1)
                idxs = np.argsort(dists)[: min(k, len(self.idx_to_id))]
                return [self.idx_to_id[i] for i in idxs]
        finally:
            if self.query_latency_metric is not None:
                self.query_latency_metric.observe(time.perf_counter() - start)
            if self.index_size_metric is not None:
                self.index_size_metric.set(len(self.idx_to_id))

    def get_vector_timestamps(self) -> Dict[str, int]:
        with self.lock:
            return dict(self.vector_ts)
