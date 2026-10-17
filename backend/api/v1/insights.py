"""Health, Dashboard and Insights (PRD §7, aggregate only per §6 FR-CHAT-09), audit log (§10)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from ...analytics import audit
from ...permissions.access import Principal
from ...permissions.roles import P
from ..deps import current_principal, get_services, require
from ..services import Services

router = APIRouter(prefix="/v1", tags=["insights"])


@router.get("/health")
def health(svc: Services = Depends(get_services)):
    """PRD §37 GET /v1/health."""
    with svc.pool.connection() as c:
        c.execute("SELECT 1")
    ev = getattr(svc, "models_ready", None)
    return {"status": "ok", "database": "ok", "models": "ready" if ev is None or ev.is_set() else "loading"}


@router.get("/dashboard")
def dashboard(actor: Principal = Depends(require(P.VIEW_DASHBOARD)), svc: Services = Depends(get_services)):
    """§7 Dashboard. Everyone who opens it governs every department (Knowledge Admin, System Admin, Founder/CEO)."""
    scope: Optional[frozenset] = None if actor.all_departments else frozenset(actor.managed_department_ids)
    return svc.analytics.dashboard(scope)


@router.get("/insights")
def insights(days: int = 30, _: Principal = Depends(require(P.VIEW_INSIGHTS)), svc: Services = Depends(get_services)):
    """§7 Insights: top questions, zero-result queries, feedback, department usage, document coverage, response latency."""
    return svc.analytics.insights(max(1, min(days, 365)))


@router.get("/failed-questions")
def failed_questions(_: Principal = Depends(require(P.MANAGE_KNOWLEDGE_GAPS)), svc: Services = Depends(get_services)):
    return {"failed_questions": svc.ops.failed_questions()}


@router.get("/knowledge-health")
def knowledge_health(_: Principal = Depends(require(P.VIEW_INSIGHTS)), svc: Services = Depends(get_services)):
    return svc.analytics.knowledge_health()


@router.get("/answer-quality")
def answer_quality(days: int = 30, _: Principal = Depends(require(P.VIEW_INSIGHTS)), svc: Services = Depends(get_services)):
    """Patterns in 👍/👎 for administrators: which sources and question types are rated badly, and how well 'high confidence' matches reality."""
    q = svc.ops.answer_quality(max(1, min(days, 365)), since=svc.ops.learning_since())
    q["learning_enabled"] = bool(svc.settings.feedback_learning)
    return q


@router.post("/learning/reset")
def reset_learning(actor: Principal = Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    """Forget everything learned from ratings so far (the ratings stay stored for the audit trail; they just stop counting)."""
    svc.ops.reset_learning(actor.user_id)
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="reset_learning")
    return {"reset": True}


@router.get("/audit-logs")
def audit_logs(event: Optional[str] = None, limit: int = 200, _: Principal = Depends(require(P.MANAGE_SYSTEM)),
               svc: Services = Depends(get_services)):
    return {"audit_logs": svc.ops.list_audit(limit, event)}
