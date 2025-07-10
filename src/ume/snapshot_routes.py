from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .api_deps import get_graph, get_current_role
from .graph_adapter import IGraphAdapter
from .snapshot import snapshot_graph_to_file, load_graph_into_existing
from .event_ledger import event_ledger
from .replay import build_graph_from_ledger
from .api_deps import configure_graph
from .config import settings

router = APIRouter(prefix="/snapshot")


class SnapshotPath(BaseModel):
    path: str


def _resolve_snapshot_path(path_str: str) -> Path:
    """Resolve ``path_str`` relative to :data:`UME_SNAPSHOT_DIR`.

    Absolute paths are allowed whenever :data:`UME_SNAPSHOT_DIR` is unset
    ("" or ".").  When the directory is set, the resulting path must remain
    within that directory or a ``400`` error is raised.
    """

    snapshot_dir = settings.UME_SNAPSHOT_DIR
    base = Path(snapshot_dir).resolve(strict=False)

    candidate = Path(path_str)
    if not candidate.is_absolute():
        candidate = base / candidate

    candidate = candidate.resolve(strict=False)

    if snapshot_dir not in {"", "."}:
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Path outside allowed directory",
            ) from exc

    return candidate


@router.post("/save")
def save_snapshot(
    req: SnapshotPath,
    graph: IGraphAdapter = Depends(get_graph),
    role: str = Depends(get_current_role),
) -> dict[str, str]:
    if role != "AnalyticsAgent":
        raise HTTPException(status_code=403, detail="Forbidden")
    path = _resolve_snapshot_path(req.path)
    snapshot_graph_to_file(graph, path)
    return {"status": "ok"}


@router.post("/load")
def load_snapshot(
    req: SnapshotPath,
    graph: IGraphAdapter = Depends(get_graph),
    role: str = Depends(get_current_role),
) -> dict[str, str]:
    if role != "AnalyticsAgent":
        raise HTTPException(status_code=403, detail="Forbidden")
    path = _resolve_snapshot_path(req.path)
    load_graph_into_existing(graph, path)
    return {"status": "ok"}


@router.post("/restore")
def restore_graph(
    req: SnapshotPath,
    graph: IGraphAdapter = Depends(get_graph),
    role: str = Depends(get_current_role),
) -> dict[str, str]:
    """Rebuild the graph database from the event ledger."""
    if role != "AnalyticsAgent":
        raise HTTPException(status_code=403, detail="Forbidden")
    if hasattr(graph, "close"):
        graph.close()
    new_graph = build_graph_from_ledger(event_ledger, db_path=req.path)
    configure_graph(new_graph)
    return {"status": "ok"}
