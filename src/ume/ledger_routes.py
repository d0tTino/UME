from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .event_ledger import event_ledger
from .persistent_graph import build_graph_from_ledger
from . import api_deps as deps

router = APIRouter()


class LedgerEvent(BaseModel):
    """Representation of a single ledger entry."""

    offset: int
    event: Dict[str, Any]


@router.get("/ledger/events", response_model=List[LedgerEvent])
def list_events(
    start: int = Query(0, ge=0),
    end: int | None = Query(None, ge=0),
    limit: int | None = Query(None, ge=1),
    _: str = Depends(deps.get_current_role),
) -> List[LedgerEvent]:
    """Return ledger events starting at ``start`` up to ``end`` (inclusive)."""

    entries = event_ledger.range(start=start, end=end, limit=limit)
    return [LedgerEvent(offset=o, event=e) for o, e in entries]


@router.get("/ledger/replay")
def replay_ledger(
    end_offset: int | None = Query(None, ge=0),
    end_timestamp: int | None = Query(None, ge=0),
    _: str = Depends(deps.get_current_role),
) -> Dict[str, Any]:
    """Return a snapshot of the graph up to ``end_offset`` or ``end_timestamp``."""

    graph = build_graph_from_ledger(
        event_ledger, end_offset=end_offset, end_timestamp=end_timestamp
    )
    return graph.dump()


@router.get("/graph/history")
def graph_history(
    offset: int | None = Query(None, ge=0),
    timestamp: int | None = Query(None, ge=0),
    _: str = Depends(deps.get_current_role),
) -> Dict[str, Any]:
    """Return a snapshot of the graph at ``offset`` or ``timestamp``."""

    graph = build_graph_from_ledger(
        event_ledger, end_offset=offset, end_timestamp=timestamp
    )
    return graph.dump()
