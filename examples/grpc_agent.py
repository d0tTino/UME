"""Example agent usage of the gRPC AsyncUMEClient."""

import asyncio
import os
from ume_client import AsyncUMEClient


async def main() -> None:
    token = os.environ.get("UME_GRPC_TOKEN")
    async with AsyncUMEClient("localhost:50051", token=token) as client:
        result = await client.run_cypher("MATCH (n) RETURN n LIMIT 1")
        print("Cypher result:", result)

        ids = await client.search_vectors([0.0] * 1536, k=3)
        print("Vector search IDs:", ids)

        entries = await client.get_audit_entries(limit=5)
        print("Recent audit entries:", entries)


if __name__ == "__main__":
    asyncio.run(main())
