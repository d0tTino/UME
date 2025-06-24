import csv
import importlib.util
from pathlib import Path
import sys

module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "benchmarks.py"
spec = importlib.util.spec_from_file_location("ume.benchmarks", module_path)
assert spec and spec.loader
benchmarks = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = benchmarks
spec.loader.exec_module(benchmarks)


def test_benchmark_vector_store_structure():
    res = benchmarks.benchmark_vector_store(
        use_gpu=False, dim=2, num_vectors=10, num_queries=5
    )
    assert set(res.keys()) == {"build_time", "avg_query_latency"}
    assert isinstance(res["build_time"], float)
    assert isinstance(res["avg_query_latency"], float)


def test_run_benchmarks_csv(tmp_path):
    csv_path = tmp_path / "out.csv"
    results = benchmarks.run_benchmarks(
        2,
        use_gpu=False,
        dim=2,
        num_vectors=10,
        num_queries=1,
        csv_path=csv_path,
    )
    assert len(results) == 2
    with csv_path.open() as f:
        header = next(csv.reader(f))
        assert header == ["run", "build_time", "avg_query_latency"]

