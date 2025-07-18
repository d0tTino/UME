# Integration Adapters

UME ships with simple wrappers for popular frameworks. Each adapter forwards events
to a running UME instance and exposes a `send_events` and `recall` API. A
`store_events` alias using the `/store` endpoint is also available. Async variants
are provided with the `Async` prefix.

The examples below demonstrate both synchronous and asynchronous usage.

## LangGraph
See [examples/langgraph_integration.ipynb](../examples/langgraph_integration.ipynb)
for a minimal demonstration of `send_events` and `recall`.
```python
from ume.integrations import LangGraph, AsyncLangGraph

# Sync
client = LangGraph()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncLangGraph() as client:
        await client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## Letta
See [examples/letta_integration.ipynb](../examples/letta_integration.ipynb) for
a minimal demonstration of `send_events` and `recall`.
```python
from ume.integrations import Letta, AsyncLetta

# Sync
client = Letta()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncLetta() as client:
        await client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## MemGPT
See [examples/memgpt_integration.ipynb](../examples/memgpt_integration.ipynb)
for a minimal demonstration of `send_events` and `recall`.
```python
from ume.integrations import MemGPT, AsyncMemGPT

# Sync
client = MemGPT()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncMemGPT() as client:
        await client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## CrewAI
See [examples/crewai_integration.ipynb](../examples/crewai_integration.ipynb)
for a minimal demonstration of `send_events` and `recall`.
```python
from ume.integrations import CrewAI, AsyncCrewAI

# Sync
client = CrewAI()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncCrewAI() as client:
        await client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## AutoGen
See [examples/autogen_integration.ipynb](../examples/autogen_integration.ipynb)
for a minimal demonstration of `send_events` and `recall`.
```python
from ume.integrations import AutoGen, AsyncAutoGen

# Sync
client = AutoGen()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncAutoGen() as client:
        await client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```

## SuperMemory
See [examples/supermemory_integration.ipynb](../examples/supermemory_integration.ipynb)
for a minimal demonstration of `send_events` and `recall`.
```python
from ume.integrations import SuperMemory, AsyncSuperMemory

# Sync
client = SuperMemory()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))

# Async
async def main():
    async with AsyncSuperMemory() as client:
        await client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
        print(await client.recall({"node_id": "n1"}))
```
