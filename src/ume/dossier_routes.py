from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import api_deps as deps
from .policy import (
    can_modify_telemetry,
    can_read_projects,
    can_read_reflections,
    can_read_skills,
    can_read_values,
    can_read_memories,
)
from .config import settings
from .audit import log_audit_entry


from .dossier import (
    Dossier,
    add_project as dossier_add_project,
    add_reflection,
    add_memory,
    add_value,
    add_skill,
    add_goal,
    list_projects,
    list_reflections,
    list_values,
    list_skills,
    list_goals,
    list_memories,
    update_preferences,
    update_shareable_flags,
)

router = APIRouter(prefix="/dossier")


def _dossier_path(dossier_id: str) -> Path:
    """Return the filesystem path for ``dossier_id``."""
    base = Path(settings.UME_DOSSIER_PATH).expanduser()
    return base / dossier_id


class AddProjectRequest(BaseModel):
    dossier_id: str
    project_id: str


class AddReflectionRequest(BaseModel):
    dossier_id: str
    text: str
    links: list[str] | None = None
    attachments: list[str] | None = None


class AddMemoryRequest(BaseModel):
    dossier_id: str
    text: str
    links: list[str] | None = None
    attachments: list[str] | None = None


class SetPreferenceRequest(BaseModel):
    dossier_id: str
    key: str
    value: Any


class SetShareableRequest(BaseModel):
    dossier_id: str
    shareable: bool | None = None
    shareable_projects: bool | None = None
    shareable_reflections: bool | None = None
    shareable_skills: bool | None = None
    shareable_values: bool | None = None
    shareable_memories: bool | None = None


class AddValueRequest(BaseModel):
    dossier_id: str
    value: str


class AddSkillRequest(BaseModel):
    dossier_id: str
    skill: str


class AddGoalRequest(BaseModel):
    dossier_id: str
    goal: str


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
    log_audit_entry(settings.UME_AGENT_ID, f"view_dossier {dossier_id}")
    return {
        "dossier_id": dossier_id,
        "projects": list_projects(dossier),
        "shareable_projects": dossier.shareable_projects,
        "shareable_reflections": dossier.shareable_reflections,
        "shareable_skills": dossier.shareable_skills,
        "shareable_values": dossier.shareable_values,
        "shareable_memories": dossier.shareable_memories,
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
    log_audit_entry(settings.UME_AGENT_ID, f"add_project {req.project_id}")
    return cast(
        Dict[str, object],
        {
            "dossier_id": req.dossier_id,
            "projects": list_projects(dossier),
            "shareable_projects": dossier.shareable_projects,
            "shareable_reflections": dossier.shareable_reflections,
            "shareable_skills": dossier.shareable_skills,
            "shareable_values": dossier.shareable_values,
            "shareable_memories": dossier.shareable_memories,
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
    add_reflection(dossier, req.text, req.links, req.attachments)
    log_audit_entry(settings.UME_AGENT_ID, f"add_reflection {req.dossier_id}")
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
    add_memory(dossier, req.text, req.links, req.attachments)
    log_audit_entry(settings.UME_AGENT_ID, f"add_memory {req.dossier_id}")
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
    log_audit_entry(settings.UME_AGENT_ID, f"set_pref {req.dossier_id} {req.key}")
    return {"status": "ok"}


@router.post("/set-shareable")
def set_shareable(
    req: SetShareableRequest, role: str = Depends(deps.get_current_role)
) -> Dict[str, str]:
    """Update shareable flags in ``meta.yaml``."""
    if role != "ProjectManager":
        raise HTTPException(status_code=403, detail="Not authorized")
    path = _dossier_path(req.dossier_id)
    dossier = Dossier.load(path) if path.exists() else Dossier.init_dossier(path)
    flags = {
        k: v
        for k, v in req.dict().items()
        if k != "dossier_id" and v is not None
    }
    update_shareable_flags(dossier, **flags)
    log_audit_entry(
        settings.UME_AGENT_ID,
        f"set_shareable {req.dossier_id} {','.join(flags.keys())}",
    )
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
    log_audit_entry(settings.UME_AGENT_ID, f"add_value {req.dossier_id}")
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
    log_audit_entry(settings.UME_AGENT_ID, f"add_skill {req.dossier_id}")
    return {"status": "ok"}


@router.post("/add-goal")
def add_goal_endpoint(
    req: AddGoalRequest, role: str = Depends(deps.get_current_role)
) -> Dict[str, str]:
    if role != "ProjectManager":
        raise HTTPException(status_code=403, detail="Not authorized")
    path = _dossier_path(req.dossier_id)
    dossier = Dossier.load(path) if path.exists() else Dossier.init_dossier(path)
    add_goal(dossier, req.goal)
    log_audit_entry(settings.UME_AGENT_ID, f"add_goal {req.dossier_id}")
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
    result = {"dossier_id": dossier_id, "projects": list_projects(dossier)}
    log_audit_entry(settings.UME_AGENT_ID, f"get_projects {dossier_id}")
    return result


@router.get("/reflections/{dossier_id}")
def get_reflections(
    dossier_id: str, role: str = Depends(deps.get_current_role)
) -> Dict[str, object]:
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_reflections(role, dossier.shareable_reflections):
        raise HTTPException(status_code=403, detail="Not authorized")
    result = {"dossier_id": dossier_id, "reflections": list_reflections(dossier)}
    log_audit_entry(settings.UME_AGENT_ID, f"get_reflections {dossier_id}")
    return result


@router.get("/skills/{dossier_id}")
def get_skills(
    dossier_id: str, role: str = Depends(deps.get_current_role)
) -> Dict[str, object]:
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_skills(role, dossier.shareable_skills):
        raise HTTPException(status_code=403, detail="Not authorized")
    result = {"dossier_id": dossier_id, "skills": list_skills(dossier)}
    log_audit_entry(settings.UME_AGENT_ID, f"get_skills {dossier_id}")
    return result


@router.get("/values/{dossier_id}")
def get_values(
    dossier_id: str, role: str = Depends(deps.get_current_role)
) -> Dict[str, object]:
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_values(role, dossier.shareable_values):
        raise HTTPException(status_code=403, detail="Not authorized")
    result = {"dossier_id": dossier_id, "values": list_values(dossier)}
    log_audit_entry(settings.UME_AGENT_ID, f"get_values {dossier_id}")
    return result


@router.get("/goals/{dossier_id}")
def get_goals(
    dossier_id: str, role: str = Depends(deps.get_current_role)
) -> Dict[str, object]:
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_skills(role):
        raise HTTPException(status_code=403, detail="Not authorized")
    result = {"dossier_id": dossier_id, "goals": list_goals(dossier)}
    log_audit_entry(settings.UME_AGENT_ID, f"get_goals {dossier_id}")
    return result


@router.get("/memories/{dossier_id}")
def get_memories(
    dossier_id: str, role: str = Depends(deps.get_current_role)
) -> Dict[str, object]:
    path = _dossier_path(dossier_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dossier not found")
    dossier = Dossier.load(path)
    if not can_read_memories(role, dossier.shareable_memories):
        raise HTTPException(status_code=403, detail="Not authorized")
    result = {"dossier_id": dossier_id, "memories": list_memories(dossier)}
    log_audit_entry(settings.UME_AGENT_ID, f"get_memories {dossier_id}")
    return result


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
    log_audit_entry(settings.UME_AGENT_ID, f"snapshot {req.dossier_id}")
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
    log_audit_entry(settings.UME_AGENT_ID, f"add_activity {req.dossier_id}")
    return {"status": "ok"}

