from fastapi import APIRouter, Depends
from pydantic import BaseModel

from . import api_deps as deps
from .recommendation_feedback import feedback_store

router = APIRouter(prefix="/feedback")


class FeedbackRequest(BaseModel):
    id: str


@router.post("/accept")
def accept_recommendation(req: FeedbackRequest, _: str = Depends(deps.get_current_role)) -> dict[str, str]:
    feedback_store.record(req.id, "accepted")
    return {"status": "ok"}


@router.post("/reject")
def reject_recommendation(req: FeedbackRequest, _: str = Depends(deps.get_current_role)) -> dict[str, str]:
    feedback_store.record(req.id, "rejected")
    return {"status": "ok"}
