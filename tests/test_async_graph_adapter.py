import pytest
from ume.async_graph_adapter import (
    AsyncPersistentGraph,
    AsyncGraphAdapterWrapper,
    apply_event_to_async_graph,
    ingest_event_async,
)
from ume.graph import MockGraph
from ume.event import Event, EventType

@pytest.mark.asyncio
async def test_async_persistent_graph_crud(tmp_path):
    graph = await AsyncPersistentGraph.create(str(tmp_path / "db.sqlite"))
    await graph.add_node("n1", {"v": 1})
    assert await graph.get_node("n1") == {"v": 1}
    await graph.update_node("n1", {"v": 2})
    assert await graph.get_node("n1") == {"v": 2}
    await graph.add_node("n2", {})
    await graph.add_edge("n1", "n2", "R")
    edges = await graph.get_all_edges()
    assert ("n1", "n2", "R", {}) in edges
    await graph.delete_edge("n1", "n2", "R")
    assert await graph.get_all_edges() == []
    await graph.clear()
    await graph.close()


@pytest.mark.asyncio
async def test_apply_event_to_async_graph_creates_node() -> None:
    graph = AsyncGraphAdapterWrapper(MockGraph())
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=0,
        payload={"node_id": "n1", "attributes": {"x": 1}},
    )
    await apply_event_to_async_graph(event, graph)
    assert await graph.get_node("n1") == {"x": 1}
    await graph.close()


@pytest.mark.asyncio
async def test_ingest_event_async_creates_node() -> None:
    graph = AsyncGraphAdapterWrapper(MockGraph())
    data = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n2",
        "payload": {"node_id": "n2", "attributes": {"y": 2}},
    }
    await ingest_event_async(data, graph)
    assert await graph.get_node("n2") == {"y": 2}
    await graph.close()

