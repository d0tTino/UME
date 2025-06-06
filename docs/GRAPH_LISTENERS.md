# Graph Listeners

UME exposes a simple listener interface that allows external components to react to changes in the knowledge graph.  A *GraphListener* is notified whenever nodes or edges are created, updated or deleted.  This is useful for triggering side effects (e.g. caching, analytics) without coupling that logic to the graph adapter itself.

## Implementing a Listener

A listener class implements the `GraphListener` protocol from `ume.listeners`.  The protocol defines four callbacks:

- `on_node_created(node_id: str, attributes: dict)`
- `on_node_updated(node_id: str, attributes: dict)`
- `on_edge_created(source_node_id: str, target_node_id: str, label: str)`
- `on_edge_deleted(source_node_id: str, target_node_id: str, label: str)`

Each callback corresponds to an event type processed by `apply_event_to_graph`.

```python
from ume import Event, EventType, MockGraph, apply_event_to_graph
from ume.listeners import register_listener, unregister_listener, GraphListener

class MyListener:
    def on_node_created(self, node_id: str, attributes: dict) -> None:
        print(f"Node {node_id} created with attributes {attributes}")

    def on_node_updated(self, node_id: str, attributes: dict) -> None:
        print(f"Node {node_id} updated with {attributes}")

    def on_edge_created(self, source: str, target: str, label: str) -> None:
        print(f"Edge {label} from {source} to {target} created")

    def on_edge_deleted(self, source: str, target: str, label: str) -> None:
        print(f"Edge {label} from {source} to {target} deleted")

listener = MyListener()
register_listener(listener)

# Create a node
event = Event(EventType.CREATE_NODE, timestamp=0, payload={"node_id": "n1", "attributes": {"name": "test"}})
apply_event_to_graph(event, MockGraph())

unregister_listener(listener)
```

## Registering and Unregistering

Use `register_listener()` to begin receiving callbacks and `unregister_listener()` when the listener is no longer needed.  You may register multiple listeners; each will receive every callback in the order they were registered.

## Event to Callback Mapping

| EventType | Callback |
|-----------|---------|
| `CREATE_NODE` | `on_node_created` |
| `UPDATE_NODE_ATTRIBUTES` | `on_node_updated` |
| `CREATE_EDGE` | `on_edge_created` |
| `DELETE_EDGE` | `on_edge_deleted` |

All callbacks are invoked **after** the graph mutation has been successfully applied.
