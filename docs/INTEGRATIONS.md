# Integration Adapters

UME ships with simple wrappers for popular frameworks. Each adapter forwards events
to a running UME instance and exposes a `send_events` and `recall` API. Async
variants are also available with the `Async` prefix.

The examples below demonstrate both synchronous and asynchronous usage.

## LangGraph
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
