# app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any 
import pathlib 
import json 

from ume import (
    parse_event,
    apply_event_to_graph,
    load_graph_from_file,
    snapshot_graph_to_file,
    MockGraph, 
    IGraphAdapter, 
    EventError,
    ProcessingError,
    SnapshotError,
    API_SNAPSHOT_PATH # Import for auto-load/save
)

# FastAPI app instance
app = FastAPI(
    title="Universal Memory Engine (UME) API",
    description="RESTful access to UME’s event-sourced memory graph.",
    version="0.3.1-dev" 
)

# Global graph instance, initialized on startup
graph: Optional[IGraphAdapter] = None


@app.on_event("startup")
async def load_snapshot_on_startup():
    """Load graph from snapshot on API startup."""
    global graph
    try:
        print(f"API startup: Attempting to load snapshot from {API_SNAPSHOT_PATH}...", flush=True)
        graph = load_graph_from_file(API_SNAPSHOT_PATH)
        print(f"API startup: Graph loaded successfully from {API_SNAPSHOT_PATH}.", flush=True)
    except SnapshotError as e: # Catches file not found from load_graph_from_file, parse errors, structure errors
        print(f"API startup: Snapshot error ('{e}') loading from {API_SNAPSHOT_PATH}. Starting with an empty graph.", flush=True)
        graph = MockGraph()
    except Exception as e: # Catch any other unexpected error during load
        print(f"API startup: An unexpected error occurred loading snapshot from {API_SNAPSHOT_PATH}: {e}. Starting with an empty graph.", flush=True)
        graph = MockGraph() # Ensure graph is initialized even on unexpected error

@app.on_event("shutdown")
async def save_snapshot_on_shutdown():
    """Save graph to snapshot on API shutdown."""
    global graph
    if graph is not None:
        try:
            print(f"API shutdown: Attempting to save snapshot to {API_SNAPSHOT_PATH}...", flush=True)
            snapshot_graph_to_file(graph, API_SNAPSHOT_PATH) # This now handles parent dir creation
            print(f"API shutdown: Graph saved successfully to {API_SNAPSHOT_PATH}.", flush=True)
        except SnapshotError as e: 
            print(f"API shutdown: Failed to save snapshot to {API_SNAPSHOT_PATH}: {e}", flush=True)
        except Exception as e: 
            print(f"API shutdown: An unexpected error occurred while saving snapshot: {e}", flush=True)
    else:
        print("API shutdown: Graph instance not available, cannot save snapshot.", flush=True)


# ────── Request Models ──────
class EventInput(BaseModel): 
    event_type: str 
    timestamp: int
    node_id: Optional[str] = None      
    target_node_id: Optional[str] = None
    label: Optional[str] = None         
    payload: Optional[Dict[str, Any]] = None 
    event_id: Optional[str] = None      
    source: Optional[str] = None        


class SnapshotPath(BaseModel):
    path: str


# ────── Helper for Graph Initialization Check ──────
def _ensure_graph_initialized():
    if graph is None:
        # This state should ideally not be reached if startup event handler works correctly.
        # It indicates a server-side issue (graph not initialized).
        raise HTTPException(status_code=503, detail="Graph service not yet initialized. Please try again shortly.")


# ────── Endpoints ──────
@app.post("/event", summary="Submit an event to modify the graph")
def post_event_endpoint(evt_input: EventInput):
    _ensure_graph_initialized()
    try:
        event_dict = evt_input.dict(exclude_unset=True)
        event_obj = parse_event(event_dict)
        apply_event_to_graph(event_obj, graph) # graph is the global instance
    except EventError as ee:
        raise HTTPException(status_code=422, detail=f"Event validation error: {ee}")
    except ProcessingError as pe:
        raise HTTPException(status_code=400, detail=f"Processing error: {pe}")
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    return {"status": "ok", "event_id": event_obj.event_id}


@app.get("/nodes", summary="List all node IDs")
def list_nodes_endpoint():
    _ensure_graph_initialized()
    return {"nodes": graph.get_all_node_ids()}


@app.get("/edges", summary="List all edges")
def list_edges_endpoint():
    _ensure_graph_initialized()
    return {"edges": graph.get_all_edges()}


@app.get("/neighbors/{node_id}", summary="Get neighbors of a node")
def get_neighbors_endpoint(node_id: str, label: Optional[str] = None):
    _ensure_graph_initialized()
    try:
        neighbors = graph.find_connected_nodes(node_id, label)
        return {"node_id": node_id, "label_filter": label, "neighbors": neighbors}
    except ProcessingError as pe: 
        raise HTTPException(status_code=404, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.post("/snapshot/save", summary="Save graph state to JSON")
def save_snapshot_endpoint(req: SnapshotPath):
    _ensure_graph_initialized()
    try:
        snapshot_graph_to_file(graph, req.path)
        return {"status": "success", "message": f"Snapshot saved to {req.path}"}
    except SnapshotError as e: # Catch specific error from snapshot_graph_to_file
        raise HTTPException(status_code=500, detail=f"Snapshot save failed: {str(e)}")
    except Exception as e: # Catch other FS errors etc.
        raise HTTPException(status_code=500, detail=f"Snapshot save failed: {str(e)}")


@app.post("/snapshot/load", summary="Load graph state from JSON")
def load_snapshot_endpoint(req: SnapshotPath):
    global graph # Declare graph as global to allow reassignment
    # No _ensure_graph_initialized() here as we are replacing it.
    try:
        loaded_graph = load_graph_from_file(req.path)
        graph = loaded_graph 
        return {"status": "success", "message": f"Graph loaded from {req.path}"}
    except SnapshotError as e: # Catches FileNotFoundError, JSONDecodeError, structure errors from load_graph_from_file
        if "not found" in str(e).lower(): # More specific HTTP status for file not found
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=f"Snapshot load failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Snapshot load failed: {str(e)}")


@app.post("/clear", summary="Clear the graph")
def clear_graph_endpoint():
    _ensure_graph_initialized()
    try:
        graph.clear()
        return {"status": "success", "message": "Graph cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear graph: {str(e)}")

# To run this app (save as app.py in root):
# poetry run uvicorn app:app --reload
```
