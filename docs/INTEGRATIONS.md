# Integration Adapters

UME ships with simple wrappers for popular frameworks. Each adapter forwards events
to a running UME instance and exposes a `send_events` and `recall` API. Async
variants are also available with the `Async` prefix.

## LangGraph
```python
from ume.integrations import LangGraph

client = LangGraph()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))
```

## Letta
```python
from ume.integrations import Letta

client = Letta()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))
```

## MemGPT
```python
from ume.integrations import MemGPT

client = MemGPT()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))
```

## CrewAI
```python
from ume.integrations import CrewAI

client = CrewAI()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))
```

## AutoGen
```python
from ume.integrations import AutoGen

client = AutoGen()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))
```

## SuperMemory
```python
from ume.integrations import SuperMemory

client = SuperMemory()
client.send_events([{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1"}])
print(client.recall({"node_id": "n1"}))
```
