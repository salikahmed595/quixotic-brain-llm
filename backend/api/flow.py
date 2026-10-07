"""Knowledge workflow actions (PRD §12.3) shared by the knowledge and document routes."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException

from ..analytics import audit
from ..permissions.access import PermissionDenied, Principal
from ..permissions.workflow import (ACTIVE, APPROVED, ARCHIVED, PENDING, REJECTED, SUBMITTED, check_transition)
from .services import Services

_AUDIT_FOR = {SUBMITTED: audit.KNOWLEDGE_SUBMISSION, APPROVED: audit.APPROVAL, REJECTED: audit.REJECTION,
              ARCHIVED: audit.ARCHIVE_EVENT, ACTIVE: audit.ADMIN_ACTION}


class KnowledgeFlow:
    def __init__(self, svc: Services) -> None:
        self.svc = svc

    def enqueue(self, job_type: str, payload: dict, actor: Optional[UUID]) -> UUID:
        job_id = self.svc.ops.create_job(job_type, payload, actor)
        self.svc.queue.send(job_id, job_type)
        return job_id

    def transition(self, version_id: UUID, to_status: str, actor: Principal, note: Optional[str] = None) -> dict:
        v = self.svc.knowledge.get_version(version_id)
        if v is None:
            raise HTTPException(404, "knowledge version not found")
        try:
            check_transition(actor, v["status"], to_status, v["department_ids"], v["created_by"])
        except PermissionDenied as e:
            raise HTTPException(403, str(e))
        prev = self.svc.knowledge.transition(version_id, to_status, actor.user_id, note)
        audit.record(self.svc.ops, _AUDIT_FOR.get(to_status, audit.ADMIN_ACTION), actor.user_id, actor.employee_id,
                     version_id=version_id, title=v["title"], from_status=prev, to_status=to_status)
        job_id = None
        if to_status == SUBMITTED:
            if not v["source_file_id"]:                      # uploaded files are processed at upload time (§13)
                job_id = self.enqueue("knowledge.index", {"version_id": str(version_id)}, actor.user_id)
            self.svc.knowledge.transition(version_id, PENDING, None, "submitted for review")   # §12.3 next step
            to_status = PENDING
        return {"version_id": str(version_id), "status": to_status, "job_id": str(job_id) if job_id else None}

    def admin_publish(self, version_id: UUID, actor: Principal) -> None:
        """Administrator direct publish: walk every step of the §12.3 chain (each one is checked and audited)."""
        if self.svc.knowledge.get_version(version_id)["status"] == "draft":
            self.transition(version_id, SUBMITTED, actor)          # also moves it to pending_review
        self.transition(version_id, APPROVED, actor)
        self.transition(version_id, ACTIVE, actor)
