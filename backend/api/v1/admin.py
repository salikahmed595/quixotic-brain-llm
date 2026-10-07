"""Administration — PRD §9.4, §10, §40, §47 (route names are not in the PRD)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...analytics import audit
from ...auth.security import generate_api_key, hash_password
from ...permissions.access import Principal
from ...permissions.roles import P, Role
from ..deps import KEY_PERMISSIONS, get_services, require
from ..flow import KnowledgeFlow
from ..services import Services

router = APIRouter(prefix="/v1", tags=["admin"])


# ---- users (§9.4 manage users / permissions) ----
class UserCreate(BaseModel):
    employee_id: str
    email: str
    full_name: str
    password: str = Field(min_length=8)
    role: Role
    department_ids: list[UUID] = []


class UserUpdate(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    department_ids: Optional[list[UUID]] = None


@router.get("/users")
def list_users(_: Principal = Depends(require(P.MANAGE_USERS)), svc: Services = Depends(get_services)):
    return {"users": svc.users.list_users()}


@router.post("/users", status_code=201)
def create_user(body: UserCreate, actor: Principal = Depends(require(P.MANAGE_USERS)), svc: Services = Depends(get_services)):
    uid = svc.users.create_user(body.employee_id, body.email, body.full_name, hash_password(body.password), body.role,
                                body.department_ids)
    audit.record(svc.ops, audit.PERMISSION_CHANGE, actor.user_id, actor.employee_id, created_user=uid, role=body.role.value)
    return {"id": str(uid)}


@router.patch("/users/{user_id}")
def update_user(user_id: UUID, body: UserUpdate, actor: Principal = Depends(require(P.MANAGE_PERMISSIONS)),
                svc: Services = Depends(get_services)):
    if svc.users.get(user_id) is None:
        raise HTTPException(404, "user not found")
    svc.users.update_user(user_id, body.role, body.is_active, body.department_ids)
    audit.record(svc.ops, audit.PERMISSION_CHANGE, actor.user_id, actor.employee_id, user=user_id,
                 role=body.role.value if body.role else None, is_active=body.is_active,
                 department_ids=[str(d) for d in body.department_ids] if body.department_ids is not None else None)
    return {"id": str(user_id)}


# ---- access requests: approve people who created their own account (owner request) ----
class Approval(BaseModel):
    role: Role = Role.EMPLOYEE
    department_ids: list[UUID] = Field(min_length=1)


MANAGER_MAY_GRANT = (Role.EMPLOYEE, Role.CONTRIBUTOR)


def _request_scope(p: Principal):
    return None if p.role is Role.ADMINISTRATOR else p.department_ids


@router.get("/access-requests")
def access_requests(p: Principal = Depends(require(P.REVIEW_DEPARTMENT_SUBMISSIONS)), svc: Services = Depends(get_services)):
    """Administrator: every waiting sign-up. Manager: those that asked for one of their departments (or for none)."""
    out = []
    for r in svc.users.pending_requests(_request_scope(p)):
        rid = r["requested_department_id"]
        out.append({**r, "id": str(r["id"]), "requested_department_id": str(rid) if rid else None})
    return {"requests": out}


def _own_request(svc, p, user_id):
    r = next((x for x in svc.users.pending_requests(_request_scope(p)) if x["id"] == user_id), None)
    if r is None:
        raise HTTPException(404, "request not found (it may already be decided)")
    return r


@router.post("/access-requests/{user_id}/approve")
def approve_request(user_id: UUID, body: Approval, p: Principal = Depends(require(P.REVIEW_DEPARTMENT_SUBMISSIONS)),
                    svc: Services = Depends(get_services)):
    _own_request(svc, p, user_id)
    if p.role is not Role.ADMINISTRATOR:
        if body.role not in MANAGER_MAY_GRANT:
            raise HTTPException(403, "managers can approve employees and contributors only")
        if not set(body.department_ids) <= set(p.department_ids):
            raise HTTPException(403, "you can only give access to departments you belong to")
    elif not set(body.department_ids) <= svc.users.all_department_ids():
        raise HTTPException(422, "unknown department")
    if not svc.users.decide_request(user_id, True, body.role, body.department_ids, p.user_id):
        raise HTTPException(409, "this request was already decided")
    audit.record(svc.ops, audit.PERMISSION_CHANGE, p.user_id, p.employee_id, action="signup_approved", user=user_id,
                 role=body.role.value, department_ids=[str(d) for d in body.department_ids])
    return {"approved": True}


@router.post("/access-requests/{user_id}/reject")
def reject_request(user_id: UUID, p: Principal = Depends(require(P.REVIEW_DEPARTMENT_SUBMISSIONS)), svc: Services = Depends(get_services)):
    _own_request(svc, p, user_id)
    if not svc.users.decide_request(user_id, False, None, [], p.user_id):
        raise HTTPException(409, "this request was already decided")
    audit.record(svc.ops, audit.PERMISSION_CHANGE, p.user_id, p.employee_id, action="signup_rejected", user=user_id)
    return {"rejected": True}


class BulkDepartments(BaseModel):
    user_ids: list[UUID] = Field(min_length=1, max_length=1000)
    add: list[UUID] = []
    remove: list[UUID] = []


@router.post("/users/bulk-departments")
def bulk_departments(body: BulkDepartments, actor: Principal = Depends(require(P.MANAGE_PERMISSIONS)),
                     svc: Services = Depends(get_services)):
    """Give many people (or take away) access to departments in one step - who may see which knowledge (PRD §42)."""
    if not body.add and not body.remove:
        raise HTTPException(422, "choose departments to add or remove")
    known = svc.users.all_department_ids()
    if not set(body.add + body.remove) <= known:
        raise HTTPException(422, "unknown department")
    n = svc.users.bulk_departments(body.user_ids, body.add, body.remove)
    audit.record(svc.ops, audit.PERMISSION_CHANGE, actor.user_id, actor.employee_id, bulk_users=n,
                 added=[str(d) for d in body.add], removed=[str(d) for d in body.remove])
    return {"updated": n}


# ---- departments (§10) ----
class DepartmentCreate(BaseModel):
    name: str


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None            # 'active' | 'archived'
    manager_id: Optional[UUID] = None
    clear_manager: bool = False


@router.get("/departments")
def list_departments(_: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    return {"departments": svc.users.list_departments()}


@router.post("/departments", status_code=201)
def create_department(body: DepartmentCreate, actor: Principal = Depends(require(P.MANAGE_DEPARTMENTS)),
                      svc: Services = Depends(get_services)):
    did = svc.users.create_department(body.name)
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="create_department", name=body.name)
    return {"id": str(did)}


@router.patch("/departments/{dept_id}")
def update_department(dept_id: UUID, body: DepartmentUpdate, actor: Principal = Depends(require(P.MANAGE_DEPARTMENTS)),
                      svc: Services = Depends(get_services)):
    if body.status not in (None, "active", "archived"):
        raise HTTPException(422, "status must be 'active' or 'archived'")
    svc.users.update_department(dept_id, body.name, body.status, body.manager_id, body.clear_manager)
    kind = audit.ARCHIVE_EVENT if body.status == "archived" else audit.ADMIN_ACTION
    audit.record(svc.ops, kind, actor.user_id, actor.employee_id, action="update_department", department=dept_id,
                 name=body.name, status=body.status, manager_id=body.manager_id)
    return {"id": str(dept_id)}


# ---- API keys (§40) ----
LIFETIMES = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "1w": timedelta(weeks=1),
             "1m": timedelta(days=30), "1y": timedelta(days=365), "never": None}


class ApiKeyCreate(BaseModel):
    name: str                                # a label for admins; it is NOT part of the key
    permissions: list[str]
    department_ids: list[UUID] = []          # empty = all departments the acting user can see
    expires_in: Literal["1h", "24h", "1w", "1m", "1y", "never"] = "never"    # owner decision: lifetime, not per-minute limits
    rate_limit_per_minute: Optional[int] = None    # optional (PRD §40 lists a rate limit); the UI does not ask for it


@router.post("/api-keys", status_code=201)
def create_api_key(body: ApiKeyCreate, actor: Principal = Depends(require(P.MANAGE_API_KEYS)),
                   svc: Services = Depends(get_services)):
    bad = set(body.permissions) - KEY_PERMISSIONS
    if bad or not body.permissions:
        raise HTTPException(422, f"permissions must be a non-empty subset of {sorted(KEY_PERMISSIONS)}")
    if not body.name.strip():
        raise HTTPException(422, "give the key a name")
    if body.rate_limit_per_minute is not None and body.rate_limit_per_minute < 1:
        raise HTTPException(422, "rate_limit_per_minute must be >= 1")
    life = LIFETIMES[body.expires_in]
    expires_at = datetime.now(timezone.utc) + life if life else None
    full, prefix, digest, last4 = generate_api_key()
    kid = svc.ops.create_api_key(body.name.strip(), prefix, digest, last4, body.permissions, body.department_ids,
                                 body.rate_limit_per_minute, expires_at, actor.user_id)
    audit.record(svc.ops, audit.API_KEY_CREATION, actor.user_id, actor.employee_id, name=body.name.strip(), key_id=kid,
                 expires=body.expires_in)
    return {"id": str(kid), "api_key": full, "expires_at": expires_at, "note": "store it now; it cannot be shown again"}


@router.get("/api-keys")
def list_api_keys(_: Principal = Depends(require(P.MANAGE_API_KEYS)), svc: Services = Depends(get_services)):
    return {"api_keys": svc.ops.list_api_keys()}


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_api_key(key_id: UUID, actor: Principal = Depends(require(P.MANAGE_API_KEYS)), svc: Services = Depends(get_services)):
    if not svc.ops.revoke_api_key(key_id):
        raise HTTPException(404, "active key not found")
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="revoke_api_key", key_id=key_id)


# ---- jobs (§47: the frontend shows progress) ----
@router.get("/jobs")
def list_jobs(_: Principal = Depends(require(P.VIEW_SYSTEM_HEALTH)), svc: Services = Depends(get_services)):
    return {"jobs": svc.ops.list_jobs()}


@router.get("/jobs/{job_id}")
def get_job(job_id: UUID, _: Principal = Depends(require(P.VIEW_SYSTEM_HEALTH)), svc: Services = Depends(get_services)):
    j = svc.ops.get_job(job_id)
    if j is None:
        raise HTTPException(404, "job not found")
    return j


@router.post("/admin/reindex", status_code=202)
def reindex(actor: Principal = Depends(require(P.CONFIGURE_MODELS)), svc: Services = Depends(get_services)):
    """PRD §24.2: changing the embedding model requires re-indexing documents."""
    audit.record(svc.ops, audit.MODEL_CHANGE, actor.user_id, actor.employee_id, action="reindex",
                 embedding_model=svc.embedder.name)
    return {"job_id": str(KnowledgeFlow(svc).enqueue("reindex", {}, actor.user_id))}
