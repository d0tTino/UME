#!/usr/bin/env python3
"""Benchmark query latency for the VectorStore."""

from __future__ import annotations

import argparse
import faiss

from ume.benchmarks import (
    DEF_DIM,
    DEF_NUM_VECTORS,
    DEF_QUERIES,
    benchmark_vector_store,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--use-gpu", action="store_true", help="Use GPU for FAISS")
    parser.add_argument("--dim", type=int, default=DEF_DIM, help="Vector dimension")
    parser.add_argument("--num-vectors", type=int, default=DEF_NUM_VECTORS, help="Number of vectors")
    parser.add_argument("--num-queries", type=int, default=DEF_QUERIES, help="Number of queries")
    parser.add_argument("--runs", type=int, default=1, help="Number of runs")
    args = parser.parse_args()

    if args.use_gpu and not hasattr(faiss, "StandardGpuResources"):
        raise SystemExit("FAISS was built without GPU support")

    result = benchmark_vector_store(
        args.use_gpu,
        dim=args.dim,
        num_vectors=args.num_vectors,
        num_queries=args.num_queries,
        runs=args.runs,
    )
    mode = "GPU" if args.use_gpu else "CPU"
    print(
        f"Average build time: {result['avg_build_time']:.3f}s\n"
        f"Average latency ({mode}): {result['avg_query_latency']:.6f}s per query"
    )


if __name__ == "__main__":
    main()

