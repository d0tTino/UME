"""Example consuming the path stream SSE endpoint."""

import asyncio
import httpx
from ume.config import settings


async def main() -> None:
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "GET",
            "http://localhost:8000/analytics/path/stream",
            params={"source": "a", "target": "b"},
            headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
        ) as r:
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    print("node", line[6:])
                    await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
