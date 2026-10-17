"""Knowledge entry, approval workflow and versions — PRD §12, §15 (route names are not in the PRD)."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...permissions.access import Principal, resolve_department_scope
from ...permissions.roles import P, Role, can
from ...permissions.workflow import ARCHIVED, ACTIVE, APPROVED, PENDING, REJECTED, SUBMITTED, STATUSES
from ..deps import current_principal, get_services, require
from ..flow import KnowledgeFlow
from ..services import Services

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])


class KnowledgeCreate(BaseModel):          # PRD §12.2 "Add Knowledge" form
    title: str
    department_ids: list[UUID]
    category: Optional[str] = None
    document_type: Optional[str] = None
    information: str
    access_level: Optional[str] = None
    language: Optional[str] = None


class NewVersion(BaseModel):
    information: str
    access_level: Optional[str] = None
    language: Optional[str] = None


class DraftUpdate(BaseModel):
    information: Optional[str] = None
    access_level: Optional[str] = None


class Transition(BaseModel):
    to: str
    note: Optional[str] = None


def _view(v: dict, history: Optional[list] = None) -> dict:
    out = {"id": str(v["id"]), "item_id": str(v["item_id"]), "title": v["title"], "category": v["category"],
           "document_type": v["document_type"], "departments": v["departments"], "department_ids": [str(d) for d in v["department_ids"]],
           "access_level": v["access_level"], "version": v["version"], "status": v["status"], "language": v["language"],
           "created_by": v["created_by"], "created_at": v["created_at"], "reviewed_by": v["reviewed_by"],
           "reviewed_at": v["reviewed_at"], "updated_by": v["updated_by"], "updated_at": v["updated_at"],
           "information": v["body"]}
    if history is not None:
        out["history"] = history
    return out


def _check_departments(actor: Principal, svc: Services, ids: list[UUID]) -> None:
    allowed = resolve_department_scope(actor, svc.users.all_department_ids())
    if not set(ids) <= allowed:
        raise HTTPException(403, "you can only add knowledge for departments you are authorized for")


@router.post("", status_code=201)
def create(body: KnowledgeCreate, actor: Principal = Depends(require(P.PROPOSE_KNOWLEDGE)),
           svc: Services = Depends(get_services)):
    if not body.department_ids:
        raise HTTPException(422, "at least one department is required")
    _check_departments(actor, svc, body.department_ids)
    item, vid = svc.knowledge.create_item_with_first_version(
        body.title, body.category, body.document_type, body.department_ids, body.information, body.language,
        body.access_level, None, actor.user_id)
    return {"item_id": str(item), "version_id": str(vid), "status": "draft"}


@router.get("")
def list_knowledge(status: Optional[str] = None, limit: int = 50, offset: int = 0,
                   actor: Principal = Depends(current_principal), svc: Services = Depends(get_services)):
    if status and status not in STATUSES:
        raise HTTPException(422, f"status must be one of {STATUSES}")
    scope = None if actor.all_departments else actor.department_ids
    rows = svc.knowledge.list_versions(statuses=[status] if status else None, department_ids=scope, limit=limit, offset=offset)
    return {"items": [_view(v) for v in rows]}


@router.get("/{version_id}")
def get_one(version_id: UUID, actor: Principal = Depends(current_principal), svc: Services = Depends(get_services)):
    v = svc.knowledge.get_version(version_id)
    if v is None:
        raise HTTPException(404, "not found")
    if not actor.all_departments and not (set(v["department_ids"]) & actor.department_ids):
        raise HTTPException(404, "not found")                       # never reveal other departments' items
    return _view(v, svc.knowledge.history(version_id))


@router.patch("/{version_id}")
def update_draft(version_id: UUID, body: DraftUpdate, actor: Principal = Depends(require(P.PROPOSE_KNOWLEDGE)),
                 svc: Services = Depends(get_services)):
    v = svc.knowledge.get_version(version_id)
    if v is None or v["status"] != "draft":
        raise HTTPException(409, "only drafts can be edited; create a new version instead")
    if not actor.all_departments and v["created_by"] != actor.user_id:
        raise HTTPException(403, "only the author can edit a draft")
    svc.knowledge.update_draft(version_id, actor.user_id, body.information, body.access_level)
    return {"version_id": str(version_id)}


@router.post("/{version_id}/transitions")
def transition(version_id: UUID, body: Transition, actor: Principal = Depends(current_principal),
               svc: Services = Depends(get_services)):
    if body.to not in STATUSES:
        raise HTTPException(422, f"to must be one of {STATUSES}")
    return KnowledgeFlow(svc).transition(version_id, body.to, actor, body.note)


@router.post("/items/{item_id}/versions", status_code=201)
def new_version(item_id: UUID, body: NewVersion, actor: Principal = Depends(require(P.PROPOSE_KNOWLEDGE)),
                svc: Services = Depends(get_services)):
    """§15: e.g. Discount Policy V2 replaces V1 once approved and activated; V1 is then archived automatically."""
    rows = [v for v in svc.knowledge.list_versions(limit=1000) if v["item_id"] == item_id]
    if not rows:
        raise HTTPException(404, "item not found")
    _check_departments(actor, svc, list(rows[0]["department_ids"]))
    vid = svc.knowledge.create_new_version(item_id, body.information, body.language, body.access_level, None, actor.user_id)
    return {"item_id": str(item_id), "version_id": str(vid), "status": "draft"}
