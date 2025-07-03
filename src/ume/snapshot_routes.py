from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .api_deps import get_graph, get_current_role
from .graph_adapter import IGraphAdapter
from .snapshot import snapshot_graph_to_file, load_graph_into_existing

router = APIRouter(prefix="/snapshot")


class SnapshotPath(BaseModel):
    path: str


@router.post("/save")
def save_snapshot(
    req: SnapshotPath,
    graph: IGraphAdapter = Depends(get_graph),
    role: str = Depends(get_current_role),
) -> dict[str, str]:
    if role != "AnalyticsAgent":
        raise HTTPException(status_code=403, detail="Forbidden")
    snapshot_graph_to_file(graph, Path(req.path))
    return {"status": "ok"}


@router.post("/load")
def load_snapshot(
    req: SnapshotPath,
    graph: IGraphAdapter = Depends(get_graph),
    role: str = Depends(get_current_role),
) -> dict[str, str]:
    if role != "AnalyticsAgent":
        raise HTTPException(status_code=403, detail="Forbidden")
    load_graph_into_existing(graph, Path(req.path))
    return {"status": "ok"}
