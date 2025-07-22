#!/usr/bin/env python3
"""Benchmark recall latency with a large number of nodes."""

from __future__ import annotations

import argparse
import asyncio
import time
from statistics import quantiles
from typing import List

import httpx
import numpy as np

DEFAULT_DIM = 1536
DEFAULT_NUM_NODES = 1_000_000
DEFAULT_QUERIES = 100


async def _get_token(
    client: httpx.AsyncClient, username: str, password: str
) -> str:
    res = await client.post(
        "/auth/token",
        data={"username": username, "password": password},
    )
    res.raise_for_status()
    data = res.json()
    token = data.get("access_token")
    assert isinstance(token, str)
    return token


async def _load_nodes(
    client: httpx.AsyncClient,
    token: str,
    *,
    dim: int,
    num_nodes: int,
    batch_size: int = 1000,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    for start in range(0, num_nodes, batch_size):
        end = min(start + batch_size, num_nodes)
        for i in range(start, end):
            vec = np.random.random(dim).astype("float32").tolist()
            node_id = f"n{i}"
            await client.post(
                "/nodes",
                json={"id": node_id, "attributes": {"embedding": vec}},
                headers=headers,
            )
            await client.post(
                "/vectors",
                json={"id": node_id, "vector": vec},
                headers=headers,
            )


async def _benchmark_recall(
    client: httpx.AsyncClient,
    token: str,
    *,
    dim: int,
    num_queries: int,
    k: int = 5,
) -> float:
    headers = {"Authorization": f"Bearer {token}"}
    latencies: List[float] = []
    for _ in range(num_queries):
        vec = np.random.random(dim).astype("float32").tolist()
        start = time.perf_counter()
        resp = await client.get(
            "/recall",
            params=[("vector", v) for v in vec] + [("k", str(k))],
            headers=headers,
        )
        resp.raise_for_status()
        latencies.append(time.perf_counter() - start)
    return quantiles(latencies, n=100)[94]


async def _run(args: argparse.Namespace) -> None:
    async with httpx.AsyncClient(base_url=args.api) as client:
        token = await _get_token(client, args.username, args.password)
        print(f"Loading {args.num_nodes} nodes...")
        await _load_nodes(
            client,
            token,
            dim=args.dim,
            num_nodes=args.num_nodes,
        )
        print("Benchmarking recall...")
        p95 = await _benchmark_recall(
            client,
            token,
            dim=args.dim,
            num_queries=args.num_queries,
        )
        print(f"p95 recall latency: {p95*1000:.2f} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--username", default="ume", help="Auth username")
    parser.add_argument("--password", default="password", help="Auth password")
    parser.add_argument("--dim", type=int, default=DEFAULT_DIM, help="Vector dimension")
    parser.add_argument(
        "--num-nodes",
        type=int,
        default=DEFAULT_NUM_NODES,
        help="Number of nodes to generate",
    )
    parser.add_argument(
        "--num-queries",
        type=int,
        default=DEFAULT_QUERIES,
        help="Number of recall queries",
    )
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":  # pragma: no cover - manual benchmark
    main()
