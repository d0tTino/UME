from __future__ import annotations

from collections import defaultdict
from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .api_deps import get_current_role

router = APIRouter(prefix="/recommendations")


class Recommendation(BaseModel):
    id: str
    action: str


RECOMMENDATIONS: list[Recommendation] = [
    Recommendation(id="rec1", action="Upgrade vector index"),
    Recommendation(id="rec2", action="Review new node attributes"),
]

FEEDBACK: dict[str, list[str]] = defaultdict(list)


@router.get("")
def get_recommendations(
    _: str = Depends(get_current_role),
) -> list[Recommendation]:
    return RECOMMENDATIONS


class RecommendationFeedback(BaseModel):
    id: str
    feedback: str


@router.post("/feedback")
def submit_feedback(
    req: RecommendationFeedback, _: str = Depends(get_current_role)
) -> Dict[str, str]:
    FEEDBACK[req.id].append(req.feedback)
    return {"status": "ok"}
