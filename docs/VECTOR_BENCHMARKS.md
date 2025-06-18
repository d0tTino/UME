# Vector Store Benchmark

The `benchmark_vector_store` utility measures how quickly the FAISS index can be built and queried.

On an RTX 4080 with 100k random vectors (dimension 1536) and 100 search queries the GPU backed store built the index in about **2.1s** and averaged **0.7ms** per query. The CPU version required roughly **9.5s** to build and **3.6ms** per query.

Run the benchmark from the CLI:

```bash
ume> benchmark_vectors --gpu --num-vectors 100000 --num-queries 100
```

or via the HTTP API:

```bash
curl -H "Authorization: Bearer <token>" \
  'http://localhost:8000/vectors/benchmark?use_gpu=true&num_vectors=100000&num_queries=100'
```
