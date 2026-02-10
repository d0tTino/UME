# Integration Adapters

UME ships with simple wrappers for popular frameworks. Each adapter forwards events
to a running UME instance and exposes a `send_events` and `recall` API. A
`store_events` alias using the `/store` endpoint is also available. Async variants
are provided with the `Async` prefix.

### Authentication
Set `UME_API_TOKEN` in your environment or pass ``api_key`` when creating a
client. The value is sent as a ``Bearer`` token in the ``Authorization``
header for all requests.

The examples below demonstrate both synchronous and asynchronous usage.

Each adapter also exposes ``recall_stream`` and ``path_stream`` for
consuming the server-sent event endpoints.
See [examples/continuous_updates.ipynb](../examples/continuous_updates.ipynb)
for a simple streaming demonstration.

## LangGraph
See [examples/langgraph_integration.ipynb](../examples/langgraph_integration.ipynb)
for a minimal demonstration of `send_events` and `recall`. A more complete
workflow is provided in
[examples/langgraph_workflow.ipynb](../examples/langgraph_workflow.ipynb).
```python
from ume.integrations import LangGraph, AsyncLangGraph

# Sync
client = LangGraph()
client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncLangGraph() as client:
        await client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## Letta
See [examples/letta_integration.ipynb](../examples/letta_integration.ipynb) for
a minimal demonstration of `send_events` and `recall`. A step-by-step workflow
is shown in
[examples/letta_workflow.ipynb](../examples/letta_workflow.ipynb).
```python
from ume.integrations import Letta, AsyncLetta

# Sync
client = Letta()
client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncLetta() as client:
        await client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## MemGPT
See [examples/memgpt_integration.ipynb](../examples/memgpt_integration.ipynb)
for a minimal demonstration of `send_events` and `recall`.
```python
from ume.integrations import MemGPT, AsyncMemGPT

# Sync
client = MemGPT()
client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncMemGPT() as client:
        await client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## CrewAI
See [examples/crewai_integration.ipynb](../examples/crewai_integration.ipynb)
for a minimal demonstration of `send_events` and `recall`.
```python
from ume.integrations import CrewAI, AsyncCrewAI

# Sync
client = CrewAI()
client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncCrewAI() as client:
        await client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## AutoGen
See [examples/autogen_integration.ipynb](../examples/autogen_integration.ipynb)
for a minimal demonstration of `send_events` and `recall`.
```python
from ume.integrations import AutoGen, AsyncAutoGen

# Sync
client = AutoGen()
client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncAutoGen() as client:
        await client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## SuperMemory
See [examples/supermemory_integration.ipynb](../examples/supermemory_integration.ipynb)
for a minimal demonstration of `send_events` and `recall`.
```python
from ume.integrations import SuperMemory, AsyncSuperMemory

# Sync
client = SuperMemory()
client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncSuperMemory() as client:
        await client.send_events([{"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## Custom Vector Backends

Third-party packages can provide additional vector store implementations. A
backend must implement the `ume.vector_store.VectorBackend` interface and
register itself using `ume.vector_backends.register_backend` or via the
`ume.vector_backends` entry point group. The
`examples/vector_backend_plugin.py` file demonstrates a minimal in-memory
backend:

```python
from ume.vector_store import VectorBackend
from ume.vector_backends import register_backend

class MemoryBackend(VectorBackend):
    def __init__(self, dim: int, **_):
        self.dim = dim
        self.vectors: dict[str, list[float]] = {}

    def add(self, item_id: str, vector: list[float], *, persist: bool = False) -> None:
        self.vectors[item_id] = list(vector)

    def add_many(self, vectors: dict[str, list[float]], *, persist: bool = False) -> None:
        for vid, vec in vectors.items():
            self.add(vid, vec)

    def delete(self, item_id: str) -> None:
        self.vectors.pop(item_id, None)

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        import numpy as np
        if not self.vectors:
            return []
        arr = np.asarray([self.vectors[i] for i in self.vectors], dtype="float32")
        q = np.asarray(vector, dtype="float32")
        dists = np.linalg.norm(arr - q, axis=1)
        ids = list(self.vectors)
        idxs = np.argsort(dists)[:k]
        return [ids[i] for i in idxs]

    # save/load omitted for brevity

register_backend("memory", MemoryBackend)
```

Expose the backend automatically by declaring an entry point in your package:

```toml
[project.entry-points."ume.vector_backends"]
memory = "yourpkg.memory_backend:MemoryBackend"
```

Setting `UME_VECTOR_BACKEND=memory` will then use the plugin when creating a
vector store.

## Custom Integration Adapters

Third-party packages can provide their own integration clients. An adapter
should extend :class:`ume.integrations.base.BaseClient` (or the async variant)
and register itself using :func:`ume.integrations.register_adapter`:

```python
from ume.integrations.base import BaseClient
from ume.integrations import register_adapter

class MyAdapter(BaseClient):
    ...  # implement any custom logic

register_adapter("my-adapter", MyAdapter)
```

The adapter can then be retrieved with
``get_adapter("my-adapter")`` and used like any built-in client.
