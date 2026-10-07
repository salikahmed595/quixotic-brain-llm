"""Dashboard (§34), failed questions (§35), knowledge health (§36), audit logs (§53), health (§37)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from ...analytics import audit
from ...permissions.access import Principal
from ...permissions.roles import P, Role, can
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
def dashboard(actor: Principal = Depends(require(P.VIEW_DEPARTMENT_ANALYTICS)), svc: Services = Depends(get_services)):
    """§9.4 administrators see all analytics; §9.3 managers see their department."""
    scope: Optional[frozenset] = None if can(actor.role, P.VIEW_ALL_ANALYTICS) else actor.managed_department_ids
    return svc.analytics.dashboard(scope)


@router.get("/failed-questions")
def failed_questions(_: Principal = Depends(require(P.VIEW_FAILED_QUERIES)), svc: Services = Depends(get_services)):
    return {"failed_questions": svc.ops.failed_questions()}


@router.get("/knowledge-health")
def knowledge_health(_: Principal = Depends(require(P.VIEW_ALL_ANALYTICS)), svc: Services = Depends(get_services)):
    return svc.analytics.knowledge_health()


@router.get("/answer-quality")
def answer_quality(days: int = 30, _: Principal = Depends(require(P.VIEW_ALL_ANALYTICS)), svc: Services = Depends(get_services)):
    """Patterns in 👍/👎 for administrators: which sources and question types are rated badly, and how well 'high confidence' matches reality."""
    q = svc.ops.answer_quality(max(1, min(days, 365)), since=svc.ops.learning_since())
    q["learning_enabled"] = bool(svc.settings.feedback_learning)
    return q


@router.post("/learning/reset")
def reset_learning(actor: Principal = Depends(require(P.CONFIGURE_MODELS)), svc: Services = Depends(get_services)):
    """Forget everything learned from ratings so far (the ratings stay stored for the audit trail; they just stop counting)."""
    svc.ops.reset_learning(actor.user_id)
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="reset_learning")
    return {"reset": True}


@router.get("/audit-logs")
def audit_logs(event: Optional[str] = None, limit: int = 200, _: Principal = Depends(require(P.VIEW_SYSTEM_HEALTH)),
               svc: Services = Depends(get_services)):
    return {"audit_logs": svc.ops.list_audit(limit, event)}
