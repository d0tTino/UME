from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np

from .vector_backends import FaissBackend

DEF_DIM = 1536
DEF_NUM_VECTORS = 100_000
DEF_QUERIES = 100


def benchmark_vector_store(
    use_gpu: bool,
    *,
    dim: int = DEF_DIM,
    num_vectors: int = DEF_NUM_VECTORS,
    num_queries: int = DEF_QUERIES,
    runs: int = 1,
) -> Dict[str, float]:
    """Populate a ``VectorStore`` and measure average build and query time."""

    build_times: List[float] = []
    latencies: List[float] = []

    for _ in range(runs):
        store = FaissBackend(dim=dim, use_gpu=use_gpu)
        vectors = np.random.random((num_vectors, dim)).astype("float32")

        start = time.perf_counter()
        store.add_many({f"v{i}": vec.tolist() for i, vec in enumerate(vectors)})
        build_times.append(time.perf_counter() - start)

        queries = np.random.random((num_queries, dim)).astype("float32")
        start = time.perf_counter()
        for q in queries:
            store.query(q.tolist(), k=5)
        latencies.append((time.perf_counter() - start) / num_queries)

    avg_build_time = sum(build_times) / runs
    avg_query_latency = sum(latencies) / runs

    return {"avg_build_time": avg_build_time, "avg_query_latency": avg_query_latency}


def run_benchmarks(
    runs: int,
    use_gpu: bool,
    *,
    dim: int = DEF_DIM,
    num_vectors: int = DEF_NUM_VECTORS,
    num_queries: int = DEF_QUERIES,
    csv_path: Path | None = None,
) -> List[Dict[str, float]]:
    """Run the vector store benchmark ``runs`` times."""

    results: List[Dict[str, float]] = []
    for _ in range(runs):
        res = benchmark_vector_store(
            use_gpu,
            dim=dim,
            num_vectors=num_vectors,
            num_queries=num_queries,
            runs=1,
        )
        results.append(res)

    if csv_path is not None:
        fieldnames = ["run", "avg_build_time", "avg_query_latency"]
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for i, res in enumerate(results, 1):
                writer.writerow({"run": i, **res})

    return results


def main(argv: Iterable[str] | None = None) -> None:
    """CLI entry point for running benchmarks."""

    parser = argparse.ArgumentParser(description="VectorStore benchmark")
    parser.add_argument("--use-gpu", action="store_true", help="Use GPU")
    parser.add_argument("--dim", type=int, default=DEF_DIM, help="Vector dimension")
    parser.add_argument(
        "--num-vectors", type=int, default=DEF_NUM_VECTORS, help="Number of vectors"
    )
    parser.add_argument(
        "--num-queries", type=int, default=DEF_QUERIES, help="Number of queries"
    )
    parser.add_argument("--runs", type=int, default=1, help="Number of runs")
    parser.add_argument("--csv", type=Path, help="Write results to CSV")
    args = parser.parse_args(list(argv) if argv is not None else None)

    results = run_benchmarks(
        args.runs,
        args.use_gpu,
        dim=args.dim,
        num_vectors=args.num_vectors,
        num_queries=args.num_queries,
        csv_path=args.csv,
    )

    for i, res in enumerate(results, 1):
        print(
            f"Run {i}: avg_build_time={res['avg_build_time']:.3f}s, "
            f"avg_query_latency={res['avg_query_latency']*1000:.3f}ms"
        )

    if len(results) > 1:
        avg_build = sum(r["avg_build_time"] for r in results) / len(results)
        avg_latency = sum(r["avg_query_latency"] for r in results) / len(results)
        print(
            f"Average build_time={avg_build:.3f}s, "
            f"avg_query_latency={avg_latency*1000:.3f}ms"
        )


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
