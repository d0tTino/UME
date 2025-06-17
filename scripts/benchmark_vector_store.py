#!/usr/bin/env python3
"""Benchmark query latency for the VectorStore."""

from __future__ import annotations

import argparse
import time
import numpy as np
import faiss

from ume.vector_store import VectorStore


DEF_DIM = 1536
DEF_NUM_VECTORS = 100_000
DEF_QUERIES = 100


def run_benchmark(use_gpu: bool, dim: int, num_vectors: int, num_queries: int) -> float:
    """Populate a store and measure average query latency."""
    store = VectorStore(dim=dim, use_gpu=use_gpu)
    vectors = np.random.random((num_vectors, dim)).astype("float32")
    for i, vec in enumerate(vectors):
        store.add(f"v{i}", vec.tolist())

    queries = np.random.random((num_queries, dim)).astype("float32")
    start = time.perf_counter()
    for q in queries:
        store.query(q.tolist(), k=5)
    end = time.perf_counter()
    return (end - start) / num_queries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--use-gpu", action="store_true", help="Use GPU for FAISS")
    parser.add_argument("--dim", type=int, default=DEF_DIM, help="Vector dimension")
    parser.add_argument("--num-vectors", type=int, default=DEF_NUM_VECTORS, help="Number of vectors")
    parser.add_argument("--num-queries", type=int, default=DEF_QUERIES, help="Number of queries")
    args = parser.parse_args()

    if args.use_gpu and not hasattr(faiss, "StandardGpuResources"):
        raise SystemExit("FAISS was built without GPU support")

    avg = run_benchmark(args.use_gpu, args.dim, args.num_vectors, args.num_queries)
    mode = "GPU" if args.use_gpu else "CPU"
    print(f"Average latency ({mode}): {avg:.6f}s per query")


if __name__ == "__main__":
    main()

