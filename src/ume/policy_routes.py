from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Response
from pydantic import BaseModel

from . import api_deps as deps
from .consent_ledger import consent_ledger
from .plugins import alignment

router = APIRouter()


class PolicySource(BaseModel):
    content: str


class ConsentEntry(BaseModel):
    user_id: str
    scope: str
    timestamp: int


class ConsentRequest(BaseModel):
    user_id: str
    scope: str


def _resolve_policy_path(name: str) -> Path:
    """Return absolute path for policy ``name`` within :data:`POLICY_DIR`."""
    from . import api  # Local import to avoid circular dependency

    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise HTTPException(status_code=400, detail="Invalid policy path")
    return (api.POLICY_DIR / path).resolve()


@router.get("/policies")
def list_policies(_: str = Depends(deps.get_current_role)) -> Dict[str, List[str]]:
    """List all available Rego policy files."""
    from . import api

    files = [p.relative_to(api.POLICY_DIR).as_posix() for p in api.POLICY_DIR.rglob("*.rego")]
    return {"policies": sorted(files)}



@router.post("/policies/reload")
def reload_policies(_: str = Depends(deps.get_current_role)) -> Dict[str, str]:
    """Reload all alignment policy plugins."""
    alignment.reload_plugins()
    return {"status": "ok"}


@router.post("/policies/{name:path}")
async def add_policy(
    name: str,
    file: UploadFile = File(...),
    _: str = Depends(deps.get_current_role),
) -> Dict[str, str]:
    """Upload a Rego policy file under ``name``."""
    path = _resolve_policy_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    with path.open("wb") as f:
        f.write(content)
    return {"status": "ok"}


@router.delete("/policies/{name:path}")
def delete_policy(name: str, _: str = Depends(deps.get_current_role)) -> Dict[str, str]:
    """Delete a policy file."""
    path = _resolve_policy_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Policy not found")
    path.unlink()
    return {"status": "ok"}


@router.get("/policies/{name:path}")
def get_policy(name: str, _: str = Depends(deps.get_current_role)) -> Response:
    """Return the raw contents of a policy file."""
    path = _resolve_policy_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Policy not found")
    return Response(path.read_text(encoding="utf-8"), media_type="text/plain")


@router.put("/policies/{name:path}")
async def update_policy(
    name: str,
    file: UploadFile = File(...),
    _: str = Depends(deps.get_current_role),
) -> Dict[str, str]:
    """Replace an existing policy file."""
    path = _resolve_policy_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Policy not found")
    content = await file.read()
    with path.open("wb") as f:
        f.write(content)
    return {"status": "ok"}


@router.post("/policies/validate")
def validate_policy(req: PolicySource, _: str = Depends(deps.get_current_role)) -> Dict[str, str]:
    """Validate Rego policy text using regopy if available."""
    try:
        from regopy import Interpreter as RegoInterpreter  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise HTTPException(status_code=500, detail="Rego support not installed") from exc
    interp = RegoInterpreter()
    try:
        interp.add_module("policy.rego", req.content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


@router.get("/consent", response_model=list[ConsentEntry])
def list_consents(_: str = Depends(deps.get_current_role)) -> list[ConsentEntry]:
    """Return all consent ledger entries."""
    entries = consent_ledger.list_consents()
    return [ConsentEntry(user_id=u, scope=s, timestamp=t) for u, s, t in entries]


@router.post("/consent")
def add_consent(req: ConsentRequest, _: str = Depends(deps.get_current_role)) -> Dict[str, str]:
    """Record consent for a user and scope."""
    consent_ledger.give_consent(req.user_id, req.scope)
    return {"status": "ok"}


@router.delete("/consent")
def remove_consent(user_id: str, scope: str, _: str = Depends(deps.get_current_role)) -> Dict[str, str]:
    """Revoke consent for a user and scope."""
    consent_ledger.revoke_consent(user_id, scope)
    return {"status": "ok"}

