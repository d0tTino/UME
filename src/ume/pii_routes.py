from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends

from .audit import get_audit_entries
from .api_deps import get_current_role

router = APIRouter(prefix="/pii")


def _redaction_count() -> int:
    entries = get_audit_entries()
    return sum(
        1 for e in entries if "payload_redacted" in str(e.get("reason", ""))
    )


@router.get("/redactions")
def pii_redactions(_: str = Depends(get_current_role)) -> Dict[str, int]:
    return {"redacted": _redaction_count()}
