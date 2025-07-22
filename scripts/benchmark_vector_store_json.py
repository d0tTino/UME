#!/usr/bin/env python3
"""Run the vector store benchmark and output JSON metrics."""

from __future__ import annotations

import argparse
import json
import importlib.util
import sys
from pathlib import Path

import faiss

module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "benchmarks.py"
spec = importlib.util.spec_from_file_location("ume.benchmarks", module_path)
assert spec and spec.loader
benchmarks = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = benchmarks
spec.loader.exec_module(benchmarks)

DEF_DIM = benchmarks.DEF_DIM
DEF_NUM_VECTORS = benchmarks.DEF_NUM_VECTORS
DEF_QUERIES = benchmarks.DEF_QUERIES
benchmark_vector_store = benchmarks.benchmark_vector_store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--use-gpu", action="store_true", help="Use GPU for FAISS")
    parser.add_argument("--dim", type=int, default=DEF_DIM, help="Vector dimension")
    parser.add_argument(
        "--num-vectors", type=int, default=DEF_NUM_VECTORS, help="Number of vectors"
    )
    parser.add_argument(
        "--num-queries", type=int, default=DEF_QUERIES, help="Number of queries"
    )
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

    print(json.dumps(result))


if __name__ == "__main__":  # pragma: no cover - manual benchmark
    main()
