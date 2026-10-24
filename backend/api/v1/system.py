"""System — PRD §7 System ("model selection, RAG tuning, embeddings, indexing jobs, integration health, backup/restore, incident
controls, audit/export, Web Search toggles"), §10 (administrative exports are audited; secrets never reach the browser).

Model and retrieval values are shown read-only: they come from server configuration (secret references, never plaintext keys)."""
from __future__ import annotations

import csv
import io
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...analytics import audit
from ...knowledge.vault import GitVault
from ...permissions.access import Principal
from ...permissions.roles import P
from ..deps import get_services, require
from ..services import Services

router = APIRouter(prefix="/v1/admin/system", tags=["system"])
INCIDENT_KEY = "incident"


def answers_paused(svc: Services) -> Optional[str]:
    """§7 incident controls: the message to show while an administrator has paused answers, else None."""
    store = getattr(svc, "system_settings", None)
    if store is None:
        return None
    try:
        state = store.get(INCIDENT_KEY) or {}
    except Exception:
        return None
    if not state.get("answers_paused"):
        return None
    return state.get("message") or "Answers are paused by an administrator. Please try again later."


@router.get("")
def system_overview(_: Principal = Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    s = svc.settings
    settings_store = svc.system_settings
    return {
        "models": {"answer_provider": s.generation_provider, "answer_model": s.generation_model_id or "not set",
                   "embeddings": f"{s.embedding_provider} ({svc.embedder.name})", "reranker": s.reranker_model or "off",
                   "query_interpretation": s.query_interpretation},
        "retrieval": {"candidates": s.candidate_count, "final_passages": s.final_chunk_count, "rerank_top_k": s.rerank_top_k,
                      "chunk_size": s.chunk_size, "chunk_overlap": s.chunk_overlap,
                      "confidence": {"rerank_high": s.confidence_high, "rerank_medium": s.confidence_medium,
                                     "vector_high": s.confidence_vector_high, "vector_medium": s.confidence_vector_medium},
                      "sensitivity_levels": {k: sorted(v) for k, v in s.sensitivity_levels.items()}},
        "security": {"admin_mfa_required": s.admin_mfa_required, "secure_cookies": s.secure_cookies, "mail_backend": s.mail_backend,
                     "session_hours": round(s.session_ttl_seconds / 3600, 1)},
        "vault": {"path": s.vault_dir, "head": GitVault(s.vault_dir).head()},
        "backups": settings_store.get("last_backup"),                      # written by python -m backend.ops.backup create
        "restore_drill": settings_store.get("last_restore_drill"),         # PRD §16 (g): written by ... backup drill
        "incident": settings_store.get(INCIDENT_KEY, {"answers_paused": False}),
        "web_search": {"enabled": s.web_search_enabled,                     # owner 2026-10-24: chat toggle, user opt-in per question
                       "reason": None if s.web_search_enabled else "QB_WEB_SEARCH_ENABLED is off"},
        "sales_history_answers": s.sales_history_enabled,
    }


class Incident(BaseModel):
    answers_paused: bool
    message: Optional[str] = Field(default=None, max_length=300)


@router.post("/incident")
def set_incident(body: Incident, p: Principal = Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    """Pause or resume answers for everyone (e.g. a wrong document was published or the model provider misbehaves)."""
    svc.system_settings.set(INCIDENT_KEY, {"answers_paused": body.answers_paused, "message": (body.message or "").strip() or None}, p.user_id)
    audit.record(svc.ops, audit.ADMIN_ACTION, p.user_id, p.employee_id, action="incident_control", answers_paused=body.answers_paused)
    return {"answers_paused": body.answers_paused}


@router.get("/audit-verify")
def verify_audit(p: Principal = Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    """PRD §10: prove the audit log has not been changed (hash chain)."""
    return svc.ops.verify_audit_chain()


@router.get("/audit-export")
def export_audit(limit: int = 10000, p: Principal = Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    """CSV of the audit log. §10: administrative exports are themselves recorded."""
    rows = svc.ops.list_audit(max(1, min(limit, 100000)))
    audit.record(svc.ops, audit.ADMIN_ACTION, p.user_id, p.employee_id, action="audit_export", rows=len(rows))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "at", "actor_id", "actor", "event", "detail"])
    for r in rows:
        w.writerow([r["id"], r["at"].isoformat(), r["actor_id"] or "", r["actor_label"] or "", r["event"], json.dumps(r["detail"], default=str)])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=quixotic-audit-log.csv"})
