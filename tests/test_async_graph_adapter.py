import pytest
from ume.async_graph_adapter import AsyncPersistentGraph

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
    assert ("n1", "n2", "R") in edges
    await graph.delete_edge("n1", "n2", "R")
    assert await graph.get_all_edges() == []
    await graph.clear()
    await graph.close()

