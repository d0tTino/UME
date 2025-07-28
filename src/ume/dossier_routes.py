from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import api_deps as deps
from .policy import can_modify_telemetry, can_read_projects

from .dossier import (
    Dossier,
    add_project as dossier_add_project,
    add_reflection,
    add_memory,
    add_value,
    add_skill,
    list_projects,
    list_reflections,
    list_values,
    list_skills,
    list_memories,
    update_preferences,
)

router = APIRouter(prefix="/dossier")


def _dossier_path(dossier_id: str) -> Path:
    """Return the filesystem path for ``dossier_id``."""
    base = Path(os.environ.get("UME_DOSSIER_PATH", "~/.ume_dossier")).expanduser()
    return base / dossier_id


class AddProjectRequest(BaseModel):
    dossier_id: str
    project_id: str


class AddReflectionRequest(BaseModel):
    dossier_id: str
    text: str
    links: list[str] | None = None


class AddMemoryRequest(BaseModel):
    dossier_id: str
    text: str
    links: list[str] | None = None


class SetPreferenceRequest(BaseModel):
    dossier_id: str
    key: str
    value: Any


class AddValueRequest(BaseModel):
    dossier_id: str
    value: str


class AddSkillRequest(BaseModel):
    dossier_id: str
    skill: str


class SnapshotRequest(BaseModel):
    dossier_id: str


class AddActivityRequest(BaseModel):
    dossier_id: str
    payload: Dict[str, Any]


@router.get("/{dossier_id}")
def view_dossier(dossier_id: str, role: str = Depends(deps.get_current_role)) -> Dict[str, object]:
    """Return information about ``dossier_id`` if the user has access."""
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_projects(role, dossier.shareable_projects):
        raise HTTPException(status_code=403, detail="Not authorized")
    return {
        "dossier_id": dossier_id,
        "projects": list_projects(dossier),
        "shareable_projects": dossier.shareable_projects,
        "shareable_reflections": dossier.shareable_reflections,
    }


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
    dossier_add_project(dossier, req.project_id)
    return cast(
        Dict[str, object],
        {
            "dossier_id": req.dossier_id,
            "projects": list_projects(dossier),
            "shareable_projects": dossier.shareable_projects,
            "shareable_reflections": dossier.shareable_reflections,
        },
    )


@router.post("/add-reflection")
def add_reflection_endpoint(
    req: AddReflectionRequest, role: str = Depends(deps.get_current_role)
) -> Dict[str, str]:
    """Append a reflection entry to the dossier."""
    if role != "ProjectManager":
        raise HTTPException(status_code=403, detail="Not authorized")
    path = _dossier_path(req.dossier_id)
    dossier = Dossier.load(path) if path.exists() else Dossier.init_dossier(path)
    add_reflection(dossier, req.text, req.links)
    return {"status": "ok"}


@router.post("/add-memory")
def add_memory_endpoint(
    req: AddMemoryRequest, role: str = Depends(deps.get_current_role)
) -> Dict[str, str]:
    """Append a knowledge entry to the dossier."""
    if role != "ProjectManager":
        raise HTTPException(status_code=403, detail="Not authorized")
    path = _dossier_path(req.dossier_id)
    dossier = Dossier.load(path) if path.exists() else Dossier.init_dossier(path)
    add_memory(dossier, req.text, req.links)
    return {"status": "ok"}


@router.post("/set-pref")
def set_preference(
    req: SetPreferenceRequest, role: str = Depends(deps.get_current_role)
) -> Dict[str, str]:
    """Update a single preference key in the dossier."""
    if role != "ProjectManager":
        raise HTTPException(status_code=403, detail="Not authorized")
    path = _dossier_path(req.dossier_id)
    dossier = Dossier.load(path) if path.exists() else Dossier.init_dossier(path)
    update_preferences(dossier, **{req.key: req.value})
    return {"status": "ok"}


@router.post("/add-value")
def add_value_endpoint(
    req: AddValueRequest, role: str = Depends(deps.get_current_role)
) -> Dict[str, str]:
    if role != "ProjectManager":
        raise HTTPException(status_code=403, detail="Not authorized")
    path = _dossier_path(req.dossier_id)
    dossier = Dossier.load(path) if path.exists() else Dossier.init_dossier(path)
    add_value(dossier, req.value)
    return {"status": "ok"}


@router.post("/add-skill")
def add_skill_endpoint(
    req: AddSkillRequest, role: str = Depends(deps.get_current_role)
) -> Dict[str, str]:
    if role != "ProjectManager":
        raise HTTPException(status_code=403, detail="Not authorized")
    path = _dossier_path(req.dossier_id)
    dossier = Dossier.load(path) if path.exists() else Dossier.init_dossier(path)
    add_skill(dossier, req.skill)
    return {"status": "ok"}


@router.get("/projects/{dossier_id}")
def get_projects(
    dossier_id: str, role: str = Depends(deps.get_current_role)
) -> Dict[str, object]:
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_projects(role, dossier.shareable_projects):
        raise HTTPException(status_code=403, detail="Not authorized")
    return {"dossier_id": dossier_id, "projects": list_projects(dossier)}


@router.get("/reflections/{dossier_id}")
def get_reflections(
    dossier_id: str, role: str = Depends(deps.get_current_role)
) -> Dict[str, object]:
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_projects(role, dossier.shareable_reflections):
        raise HTTPException(status_code=403, detail="Not authorized")
    return {"dossier_id": dossier_id, "reflections": list_reflections(dossier)}


@router.get("/skills/{dossier_id}")
def get_skills(
    dossier_id: str, role: str = Depends(deps.get_current_role)
) -> Dict[str, object]:
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_projects(role, dossier.shareable_reflections):
        raise HTTPException(status_code=403, detail="Not authorized")
    return {"dossier_id": dossier_id, "skills": list_skills(dossier)}


@router.get("/values/{dossier_id}")
def get_values(
    dossier_id: str, role: str = Depends(deps.get_current_role)
) -> Dict[str, object]:
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_projects(role, dossier.shareable_reflections):
        raise HTTPException(status_code=403, detail="Not authorized")
    return {"dossier_id": dossier_id, "values": list_values(dossier)}


@router.get("/memories/{dossier_id}")
def get_memories(
    dossier_id: str, role: str = Depends(deps.get_current_role)
) -> Dict[str, object]:
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_projects(role, dossier.shareable_reflections):
        raise HTTPException(status_code=403, detail="Not authorized")
    return {"dossier_id": dossier_id, "memories": list_memories(dossier)}


@router.post("/snapshot")
def snapshot_endpoint(
    req: SnapshotRequest, role: str = Depends(deps.get_current_role)
) -> Dict[str, str]:
    if not can_modify_telemetry(role):
        raise HTTPException(status_code=403, detail="Not authorized")
    path = _dossier_path(req.dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    dest = dossier.snapshot()
    return {"status": "ok", "path": str(dest)}


@router.post("/add-activity")
def add_activity_endpoint(
    req: AddActivityRequest, role: str = Depends(deps.get_current_role)
) -> Dict[str, str]:
    """Append an activity entry to the dossier telemetry log."""
    if not can_modify_telemetry(role):
        raise HTTPException(status_code=403, detail="Not authorized")
    path = _dossier_path(req.dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    dossier.add_activity(req.payload)
    return {"status": "ok"}

