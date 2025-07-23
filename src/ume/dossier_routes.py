from __future__ import annotations

from typing import Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import api_deps as deps
from .policy import can_read_projects

router = APIRouter(prefix="/dossier")

# In-memory storage for dossier information
_dossiers: Dict[str, Dict[str, object]] = {}


class AddProjectRequest(BaseModel):
    dossier_id: str
    project_id: str


@router.get("/{dossier_id}")
def view_dossier(dossier_id: str, role: str = Depends(deps.get_current_role)) -> Dict[str, object]:
    """Return information about ``dossier_id`` if the user has access."""
    dossier = _dossiers.get(dossier_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Dossier not found")
    if not can_read_projects(role, bool(dossier.get("shareable"))):
        raise HTTPException(status_code=403, detail="Not authorized")
    return dossier


@router.post("/add-project")
def add_project(req: AddProjectRequest, role: str = Depends(deps.get_current_role)) -> Dict[str, object]:
    """Attach ``project_id`` to the specified dossier."""
    if role != "ProjectManager":
        raise HTTPException(status_code=403, detail="Not authorized")
    dossier = _dossiers.setdefault(
        req.dossier_id,
        {"dossier_id": req.dossier_id, "projects": [], "shareable": False},
    )
    projects = dossier.setdefault("projects", [])
    if req.project_id not in projects:
        projects.append(req.project_id)
    return cast(Dict[str, object], dossier)

