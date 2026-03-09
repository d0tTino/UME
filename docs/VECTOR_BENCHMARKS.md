# Vector Store Benchmark


> Canonical architecture reference: [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md).
The `benchmark_vector_store` utility measures how quickly the FAISS index can be built and queried.
It now supports running the benchmark multiple times and reports the average build time and query latency.

On an RTX 4080 with 100k random vectors (dimension 1536) and 100 search queries the GPU backed store built the index in about **2.1s** and averaged **0.7ms** per query. The CPU version required roughly **9.5s** to build and **3.6ms** per query.

Run the benchmark from the CLI:

```bash
ume> benchmark_vectors --gpu --num-vectors 100000 --num-queries 100 --runs 3
```

or via the HTTP API:

```bash
TOKEN=$(curl -s -X POST -d "username=ume&password=password" http://localhost:8000/auth/token | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/vectors/benchmark?use_gpu=true&num_vectors=100000&num_queries=100&runs=3'

Example response:

```json
{
  "avg_build_time": 2.1,
  "avg_query_latency": 0.0007
}
```
```

## Recall Benchmark

`scripts/benchmark_recall.py` generates synthetic nodes via the HTTP API and then
times the `/recall` endpoint. The script reports the 95th percentile latency for
a series of queries.

Run the benchmark with one million nodes:

```bash
poetry run python scripts/benchmark_recall.py --num-nodes 1000000 --num-queries 100
```

Example output:

```text
Loading 1000000 nodes...
Benchmarking recall...
p95 recall latency: 12.3 ms
```
