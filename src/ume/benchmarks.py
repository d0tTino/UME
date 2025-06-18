from __future__ import annotations

import time
from typing import Dict

import numpy as np

from .vector_store import VectorStore

DEF_DIM = 1536
DEF_NUM_VECTORS = 100_000
DEF_QUERIES = 100


def benchmark_vector_store(
    use_gpu: bool,
    *,
    dim: int = DEF_DIM,
    num_vectors: int = DEF_NUM_VECTORS,
    num_queries: int = DEF_QUERIES,
) -> Dict[str, float]:
    """Populate a ``VectorStore`` and measure build time and query latency."""

    store = VectorStore(dim=dim, use_gpu=use_gpu)
    vectors = np.random.random((num_vectors, dim)).astype("float32")

    start = time.perf_counter()
    for i, vec in enumerate(vectors):
        store.add(f"v{i}", vec.tolist())
    build_time = time.perf_counter() - start

    queries = np.random.random((num_queries, dim)).astype("float32")
    start = time.perf_counter()
    for q in queries:
        store.query(q.tolist(), k=5)
    avg_latency = (time.perf_counter() - start) / num_queries

    return {"build_time": build_time, "avg_query_latency": avg_latency}
