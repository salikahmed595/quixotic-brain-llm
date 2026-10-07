"""POST /v1/feedback — PRD §21 (helpful / not helpful; sales outcome) and §37."""
from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...permissions.roles import P, can
from ..deps import Caller, api_caller, get_services, resolve_caller
from ..services import Services

router = APIRouter(prefix="/v1", tags=["feedback"])


class FeedbackRequest(BaseModel):
    query_id: UUID
    user_id: Optional[str] = None
    helpful: Optional[bool] = None                       # §21 👍 / 👎
    outcome: Optional[Literal["sale_closed", "sale_lost", "customer_still_deciding", "follow_up_required"]] = None   # §21
    agent_action: Optional[str] = None                   # §21 "Agent action"
    note: Optional[str] = None


@router.post("/feedback", status_code=201)
def feedback(body: FeedbackRequest, caller: Caller = Depends(api_caller("feedback")), svc: Services = Depends(get_services)):
    caller = resolve_caller(caller, body.user_id, svc)
    if not can(caller.principal.role, P.SUBMIT_FEEDBACK):
        raise HTTPException(403, "your role cannot submit feedback")
    if body.helpful is None and body.outcome is None and not body.note:
        raise HTTPException(422, "send helpful, outcome or note")
    q = svc.ops.get_query(body.query_id)
    if q is None or q["user_id"] != caller.principal.user_id:
        raise HTTPException(404, "question not found")
    fid = svc.ops.add_feedback(body.query_id, caller.principal.user_id, body.helpful, body.outcome, body.agent_action, body.note)
    return {"id": str(fid), "validated": False}          # becomes searchable memory only after validation (§21)
