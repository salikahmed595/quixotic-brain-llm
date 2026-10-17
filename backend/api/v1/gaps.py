"""Missing knowledge — PRD §6 FR-CHAT-04 ("Offer Report missing information"), §9 knowledge gap loop, §11 `GET /admin/knowledge-gaps`.

Employees report; the gap is de-duplicated and routed to its department's reviewers; Knowledge Admins triage the unassigned ones;
publishing the change that answers it resolves it. Admin views show counts and comments, never who asked (§6 FR-CHAT-09)."""
from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...analytics import audit
from ...notifications.mail import send_safely
from ...permissions.access import Principal
from ...permissions.roles import P, can
from ..deps import get_services, require
from ..services import Services

router = APIRouter(prefix="/v1", tags=["knowledge-gaps"])


def gap_department(svc: Services, p: Principal, requested: Optional[UUID]) -> Optional[UUID]:
    """The department that owns a gap: the department the question was asked in, or the asker's only department; otherwise
    unassigned for Knowledge Admins to triage (the PRD says "the correct department owner" without a rule; docs/PRD_GAPS.md)."""
    if requested:
        return requested
    active = svc.users.all_department_ids()
    mine = [d for d in p.department_ids if d in active]
    return mine[0] if len(mine) == 1 else None


def record_gap(svc: Services, p: Principal, question: str, requested: Optional[UUID]) -> Optional[UUID]:
    store = getattr(svc, "gaps", None)
    if store is None:
        return None
    dept = gap_department(svc, p, requested)
    gid, created = store.record(question, dept)
    bot = getattr(svc, "approvals_bot", None)
    if created and bot:
        try:
            bot.notify_department(dept, f"\"{question[:300]}\"\n\n{svc.settings.public_url}/#/knowledge")
        except Exception:
            pass
    if created:
        for r in (svc.users.reviewers_for([dept]) if dept else []):
            if getattr(svc, "mailer", None):
                send_safely(svc.mailer, r["email"], "New question without an approved answer",
                            f"Employees asked something the knowledge base does not answer yet:\n\n\"{question[:300]}\"\n\n"
                            f"{svc.settings.public_url}/#/knowledge?gaps=1")
    return gid


class Report(BaseModel):
    query_id: UUID
    comment: Optional[str] = Field(default=None, max_length=1000)


@router.post("/knowledge-gaps/report", status_code=201)
def report_missing(body: Report, p: Principal = Depends(require(P.REPORT_MISSING_INFORMATION)), svc: Services = Depends(get_services)):
    """FR-CHAT-04 "Report missing information" for one of the person's own questions."""
    q = svc.ops.get_query(body.query_id)
    if not q or q["user_id"] != p.user_id:
        raise HTTPException(404, "question not found")
    gid = q.get("gap_id") or record_gap(svc, p, q["original_query"], q.get("department_id"))
    svc.gaps.report(gid, p.user_id, body.query_id, (body.comment or "").strip() or None)
    audit.record(svc.ops, audit.KNOWLEDGE_SUBMISSION, p.user_id, p.employee_id, action="missing_information_reported", gap=gid)
    return {"gap_id": str(gid), "status": "reported"}


def _scope(p: Principal):
    """Knowledge Admins / System Admins / CEO: every gap. Reviewers: their departments (and unassigned ones they can triage? no)."""
    if can(p.role, P.MANAGE_KNOWLEDGE_GAPS) or p.all_departments:
        return None, True
    return frozenset(p.managed_department_ids), False


@router.get("/admin/knowledge-gaps")
def list_gaps(status: Literal["open", "in_progress", "resolved", "dismissed", "active"] = "active",
              p: Principal = Depends(require(P.VIEW_KNOWLEDGE)), svc: Services = Depends(get_services)):
    depts, unassigned = _scope(p)
    statuses = ["open", "in_progress"] if status == "active" else [status]
    rows = svc.gaps.list(statuses, depts, include_unassigned=unassigned)
    return {"gaps": [{**r, "id": str(r["id"]), "department_id": str(r["department_id"]) if r["department_id"] else None,
                      "proposal_id": str(r["proposal_id"]) if r["proposal_id"] else None, "comments": (r["comments"] or [])[:5]}
                     for r in rows], "counts": svc.gaps.counts()}


class GapUpdate(BaseModel):
    status: Optional[Literal["open", "in_progress", "dismissed"]] = None
    department_id: Optional[UUID] = None
    unassign: bool = False
    note: Optional[str] = Field(default=None, max_length=1000)


@router.patch("/admin/knowledge-gaps/{gap_id}")
def update_gap(gap_id: UUID, body: GapUpdate, p: Principal = Depends(require(P.VIEW_KNOWLEDGE)), svc: Services = Depends(get_services)):
    gap = svc.gaps.get(gap_id)
    depts, _ = _scope(p)
    if gap is None or (depts is not None and gap["department_id"] not in depts):
        raise HTTPException(404, "gap not found")
    if (body.department_id or body.unassign) and depts is not None:
        raise HTTPException(403, "only Knowledge Admins can move a gap to another department")
    if body.department_id and body.department_id not in svc.users.all_department_ids():
        raise HTTPException(422, "unknown department")
    if body.status == "dismissed" and not (body.note or "").strip():
        raise HTTPException(422, "say why it is dismissed (e.g. out of scope, duplicate)")
    svc.gaps.update(gap_id, body.status, body.department_id, body.unassign, body.note, p.user_id)
    audit.record(svc.ops, audit.ADMIN_ACTION, p.user_id, p.employee_id, action="knowledge_gap_updated", gap=gap_id, status=body.status)
    return {"id": str(gap_id)}
