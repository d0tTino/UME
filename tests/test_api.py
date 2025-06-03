# tests/test_api.py
import json
import os
import pytest
from fastapi.testclient import TestClient
import pathlib # For tmp_path type hint if needed, and path operations
from pathlib import Path # Explicit import for type hint Path
import ume.config as ume_config # Added for API_SNAPSHOT_PATH monkeypatching

# Import the FastAPI app instance from app.py
# To make this work, app.py must be findable.
# If tests are run from root, and app.py is in root, 'from app import app, graph' works.
# If app.py is in src/ume/api/app.py, then 'from ume.api.app import app, graph'
# Assuming app.py is in the project root as per plan.
from app import app 

# The global graph instance is also imported to be cleared by a fixture.
# This is a common pattern for testing FastAPI apps with global state.
# For more complex scenarios, dependency injection might be used in FastAPI.
from app import graph as global_api_graph


client = TestClient(app)

@pytest.fixture(autouse=True)
def isolate_api_snapshot(tmp_path: Path, monkeypatch):
    """
    Redirects the API's default snapshot path (API_SNAPSHOT_PATH) to a temporary file
    for each test, ensuring test isolation for file-based persistence.
    Cleans up the temporary snapshot file before and after the test.
    """
    fake_snapshot_file = tmp_path / "api_isolated_snapshot.json"
    monkeypatch.setattr(ume_config, "API_SNAPSHOT_PATH", fake_snapshot_file)
    
    if fake_snapshot_file.exists():
        fake_snapshot_file.unlink() # Ensure clean state before test
        
    yield # Test runs here
    
    # Cleanup after test
    if fake_snapshot_file.exists():
        try:
            fake_snapshot_file.unlink()
        except OSError: # Handle potential race conditions or permissions issues in cleanup
            pass

@pytest.fixture(autouse=True)
def clear_graph_before_each_test():
    """Fixture to clear the global graph instance before each test."""
    global_api_graph.clear()
    yield # Test runs here
    global_api_graph.clear() # Cleanup after test if needed, though clear before is usually sufficient

def test_post_create_node_event_and_verify():
    """Test creating a node via /event and verifying with /nodes."""
    event_payload = {
        "event_type": "CREATE_NODE",
        "timestamp": int(pathlib.Path(__file__).stat().st_mtime), # Using file mod time for a consistent timestamp
        "node_id": "node_api_1",
        "payload": {"name": "API Test Node", "value": 123}
    }
    response_post = client.post("/event", json=event_payload)
    assert response_post.status_code == 200
    data_post = response_post.json()
    assert data_post["status"] == "ok"
    assert "event_id" in data_post

    response_get = client.get("/nodes")
    assert response_get.status_code == 200
    data_get = response_get.json()
    assert "node_api_1" in data_get["nodes"]

def test_post_invalid_event_missing_node_id_for_create():
    """Test posting an invalid CREATE_NODE event (missing node_id)."""
    event_payload = {
        "event_type": "CREATE_NODE",
        "timestamp": int(pathlib.Path(__file__).stat().st_mtime),
        # "node_id" is missing
        "payload": {"name": "Invalid Node"}
    }
    response = client.post("/event", json=event_payload)
    assert response.status_code == 422 # Event validation error from parse_event
    assert "Event validation error" in response.json()["detail"]
    assert "Missing required field 'node_id' for CREATE_NODE event" in response.json()["detail"]


def test_create_list_edges_and_neighbors(tmp_path: pathlib.Path): # Added tmp_path, though not used by this specific test
    """Test creating nodes, an edge, then listing edges and neighbors via API."""
    # Create two nodes
    ts = int(pathlib.Path(__file__).stat().st_mtime)
    client.post("/event", json={"event_type": "CREATE_NODE", "timestamp": ts, "node_id": "nodeA", "payload": {"name": "A"}})
    client.post("/event", json={"event_type": "CREATE_NODE", "timestamp": ts + 1, "node_id": "nodeB", "payload": {"name": "B"}})

    # Create an edge A -> B
    edge_payload = {
        "event_type": "CREATE_EDGE",
        "timestamp": ts + 2,
        "node_id": "nodeA",         # Source
        "target_node_id": "nodeB",
        "label": "connects_to"
    }
    response_edge_create = client.post("/event", json=edge_payload)
    assert response_edge_create.status_code == 200

    # Verify with /edges
    response_get_edges = client.get("/edges")
    assert response_get_edges.status_code == 200
    edges_data = response_get_edges.json()
    assert ["nodeA", "nodeB", "connects_to"] in edges_data["edges"]

    # Verify with /neighbors
    response_get_neighbors = client.get("/neighbors/nodeA")
    assert response_get_neighbors.status_code == 200
    neighbors_data = response_get_neighbors.json()
    assert "nodeB" in neighbors_data["neighbors"]
    
    response_get_neighbors_filtered = client.get("/neighbors/nodeA?label=connects_to")
    assert response_get_neighbors_filtered.status_code == 200
    assert "nodeB" in response_get_neighbors_filtered.json()["neighbors"]

    response_get_neighbors_wrong_label = client.get("/neighbors/nodeA?label=WRONG_LABEL")
    assert response_get_neighbors_wrong_label.status_code == 200
    assert response_get_neighbors_wrong_label.json()["neighbors"] == []


def test_delete_edge_via_event_and_error_cases(tmp_path: pathlib.Path):
    """Test deleting an edge via /event and error case for non-existent edge."""
    ts = int(pathlib.Path(__file__).stat().st_mtime)
    # Setup nodes and an edge
    client.post("/event", json={"event_type": "CREATE_NODE", "timestamp": ts, "node_id": "nodeX", "payload": {}})
    client.post("/event", json={"event_type": "CREATE_NODE", "timestamp": ts + 1, "node_id": "nodeY", "payload": {}})
    client.post("/event", json={"event_type": "CREATE_EDGE", "timestamp": ts + 2, "node_id": "nodeX", "target_node_id": "nodeY", "label": "relation_xy"})

    # Delete the edge
    delete_edge_payload = {
        "event_type": "DELETE_EDGE",
        "timestamp": ts + 3,
        "node_id": "nodeX",
        "target_node_id": "nodeY",
        "label": "relation_xy"
    }
    response_delete = client.post("/event", json=delete_edge_payload)
    assert response_delete.status_code == 200
    assert response_delete.json()["status"] == "ok"

    # Verify edge is gone
    response_get_edges = client.get("/edges")
    assert ["nodeX", "nodeY", "relation_xy"] not in response_get_edges.json()["edges"]

    # Attempt to delete again (should fail as edge no longer exists)
    response_delete_again = client.post("/event", json=delete_edge_payload) # Use same payload
    assert response_delete_again.status_code == 400 # ProcessingError from adapter
    assert "Processing error" in response_delete_again.json()["detail"]
    assert "does not exist and cannot be deleted" in response_delete_again.json()["detail"]


def test_snapshot_save_and_load_via_api(tmp_path: pathlib.Path):
    """Test snapshot save, clear, load via API and verify graph state."""
    ts = int(pathlib.Path(__file__).stat().st_mtime)
    snapshot_file_path = tmp_path / "api_test_snapshot.json"

    # Create some graph data
    client.post("/event", json={"event_type": "CREATE_NODE", "timestamp": ts, "node_id": "snap_N1", "payload": {"data": "val1"}})
    client.post("/event", json={"event_type": "CREATE_NODE", "timestamp": ts+1, "node_id": "snap_N2", "payload": {"data": "val2"}})
    client.post("/event", json={"event_type": "CREATE_EDGE", "timestamp": ts+2, "node_id": "snap_N1", "target_node_id": "snap_N2", "label": "SNAP_LINK"})

    # Save snapshot via API
    response_save = client.post("/snapshot/save", json={"path": str(snapshot_file_path)})
    assert response_save.status_code == 200
    assert response_save.json()["status"] == "success"
    assert os.path.exists(snapshot_file_path) # Check file was actually created

    # Clear graph via API
    response_clear = client.post("/clear")
    assert response_clear.status_code == 200
    assert response_clear.json()["status"] == "success"
    
    response_get_nodes_after_clear = client.get("/nodes")
    assert response_get_nodes_after_clear.json()["nodes"] == []
    response_get_edges_after_clear = client.get("/edges")
    assert response_get_edges_after_clear.json()["edges"] == []
    
    # Load snapshot via API
    response_load = client.post("/snapshot/load", json={"path": str(snapshot_file_path)})
    assert response_load.status_code == 200
    assert response_load.json()["status"] == "success"

    # Verify graph state restored
    response_get_nodes_after_load = client.get("/nodes")
    assert "snap_N1" in response_get_nodes_after_load.json()["nodes"]
    assert "snap_N2" in response_get_nodes_after_load.json()["nodes"]
    
    response_get_edges_after_load = client.get("/edges")
    assert ["snap_N1", "snap_N2", "SNAP_LINK"] in response_get_edges_after_load.json()["edges"]

def test_get_neighbors_node_not_found(tmp_path: pathlib.Path): # Added tmp_path for consistency, though not used
    """Test /neighbors endpoint when the node_id does not exist."""
    response = client.get("/neighbors/non_existent_node")
    assert response.status_code == 404
    # Check for either "Node error" or "Node 'non_existent_node' not found"
    # as the exact phrasing might depend on where the error is caught first.
    # Given current MockGraph, it's "Node '...' not found."
    assert "Node 'non_existent_node' not found" in response.json()["detail"]
```
