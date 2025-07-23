from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import api_deps as deps
from .policy import can_read_projects
from .dossier import Dossier

router = APIRouter(prefix="/dossier")


def _dossier_path(dossier_id: str) -> Path:
    """Return the filesystem path for ``dossier_id``."""
    base = Path(os.environ.get("UME_DOSSIER_PATH", "~/.ume_dossier")).expanduser()
    return base / dossier_id


class AddProjectRequest(BaseModel):
    dossier_id: str
    project_id: str


@router.get("/{dossier_id}")
def view_dossier(dossier_id: str, role: str = Depends(deps.get_current_role)) -> Dict[str, object]:
    """Return information about ``dossier_id`` if the user has access."""
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_projects(role, dossier.shareable):
        raise HTTPException(status_code=403, detail="Not authorized")
    return {"dossier_id": dossier_id, "projects": list(dossier.projects), "shareable": dossier.shareable}


@router.post("/add-project")
def add_project(req: AddProjectRequest, role: str = Depends(deps.get_current_role)) -> Dict[str, object]:
    """Attach ``project_id`` to the specified dossier."""
    if role != "ProjectManager":
        raise HTTPException(status_code=403, detail="Not authorized")
    path = _dossier_path(req.dossier_id)
    if path.exists():
        dossier = Dossier.load(path)
    else:
        dossier = Dossier.init_dossier(path)
    if req.project_id not in dossier.projects:
        dossier.projects.append(req.project_id)
        dossier.save()
    return cast(Dict[str, object], {"dossier_id": req.dossier_id, "projects": list(dossier.projects), "shareable": dossier.shareable})

