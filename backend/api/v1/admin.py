"""Administration — PRD §5 FR-AUTH-04/05/07, §7 (Users, Access requests, Departments, API keys, System), §11 `/admin/*`.

Every route checks its own permission on the server (PRD §3: "not only by hiding sidebar links")."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...analytics import audit
from ...auth.security import generate_api_key, hash_password, password_problem
from ...notifications.mail import decision_email, reset_email, send_safely
from ...permissions.access import Principal
from ...permissions.roles import P, Role
from ...database.users import ACCOUNT_STATES, ACTIVE, ADMIN_STATE_EDGES
from ..deps import KEY_PERMISSIONS, get_services, require
from ..jobs import enqueue
from ..services import Services
from .auth import EMAIL_RE, USERNAME_RE

router = APIRouter(prefix="/v1/admin", tags=["admin"])
public = APIRouter(prefix="/v1", tags=["admin"])


def _uuid_list(xs) -> list[str]:
    return [str(x) for x in xs]


def _user_view(r: dict) -> dict:
    return {**r, "id": str(r["id"]), "department_ids": _uuid_list(r["department_ids"])}


# ---- users (§7 Users: search/add/invite/edit/suspend/deactivate; roles, departments, last login, state, audit history) ----
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: str = Field(max_length=120)
    full_name: str = Field(min_length=2, max_length=80)
    role: Role = Role.EMPLOYEE
    department_ids: list[UUID] = []
    can_publish: bool = False
    invite: bool = True                       # True: email a link to choose a password; False: set `password` now
    password: Optional[str] = Field(default=None, max_length=200)


class UserUpdate(BaseModel):
    role: Optional[Role] = None
    department_ids: Optional[list[UUID]] = None
    can_publish: Optional[bool] = None
    full_name: Optional[str] = Field(default=None, max_length=80)


class StatusChange(BaseModel):
    status: Literal["active", "suspended", "deactivated"]
    note: Optional[str] = Field(default=None, max_length=500)


def _check_departments(svc: Services, ids: list[UUID]) -> None:
    if not set(ids) <= svc.users.all_department_ids():
        raise HTTPException(422, "unknown or disabled department")


@router.get("/users")
def list_users(q: Optional[str] = None, status: Optional[str] = None,
               _: Principal = Depends(require(P.MANAGE_USERS)), svc: Services = Depends(get_services)):
    if status and status not in ACCOUNT_STATES:
        raise HTTPException(422, f"status must be one of {ACCOUNT_STATES}")
    return {"users": [_user_view(r) for r in svc.users.list_users(q, status)]}


@router.get("/users/{user_id}")
def get_user(user_id: UUID, _: Principal = Depends(require(P.MANAGE_USERS)), svc: Services = Depends(get_services)):
    row = svc.users.user_row(user_id)
    if row is None:
        raise HTTPException(404, "user not found")
    return {**_user_view(row), "status_history": svc.users.status_history(user_id),
            "audit": svc.ops.audit_for_user(user_id, 100)}


@router.post("/users", status_code=201)
def create_user(body: UserCreate, actor: Principal = Depends(require(P.MANAGE_USERS)), svc: Services = Depends(get_services)):
    username, email = body.username.strip().lower(), body.email.strip().lower()
    if not USERNAME_RE.match(username) or not EMAIL_RE.match(email):
        raise HTTPException(422, "check the username and email")
    if body.invite:
        password = secrets.token_urlsafe(32)                       # never told to anyone; the person sets their own
    else:
        if not body.password:
            raise HTTPException(422, "give a password or send an invitation")
        problem = password_problem(body.password, username, email.split("@")[0], body.full_name)
        if problem:
            raise HTTPException(422, problem)
        password = body.password
    if svc.users.username_or_email_taken(username, email):
        raise HTTPException(409, "that username or email is already taken")
    _check_departments(svc, body.department_ids)
    uid = svc.users.create_user(username, email, " ".join(body.full_name.split()), hash_password(password), body.role,
                                body.department_ids, actor.user_id, body.can_publish and body.role is not Role.EMPLOYEE)
    if body.invite:
        token = svc.one_time.issue(uid, "reset_password", svc.settings.one_time_link_ttl_seconds)
        subject, text = reset_email(body.full_name, f"{svc.settings.public_url}/#/reset?token={token}")
        send_safely(svc.mailer, email, "You are invited to Quixotic AI",
                    text.replace("Someone asked to reset the password of your Quixotic AI account", "An administrator created a Quixotic AI account for you"))
    audit.record(svc.ops, audit.PERMISSION_CHANGE, actor.user_id, actor.employee_id, action="user_created", user=uid,
                 role=body.role.value, department_ids=_uuid_list(body.department_ids), invited=body.invite)
    return {"id": str(uid)}


@router.patch("/users/{user_id}")
def update_user(user_id: UUID, body: UserUpdate, actor: Principal = Depends(require(P.MANAGE_USERS)),
                svc: Services = Depends(get_services)):
    user = svc.users.get(user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    if user_id == actor.user_id and (body.role is not None or body.can_publish is not None):
        raise HTTPException(403, "you cannot change your own role or publisher permission")     # §5 FR-AUTH-07
    if body.department_ids is not None:
        _check_departments(svc, body.department_ids)
    role = body.role or Role(user["role"])
    can_publish = body.can_publish if body.can_publish is not None else None
    if can_publish and role is Role.EMPLOYEE:
        raise HTTPException(422, "employees cannot be publishers")
    name = " ".join(body.full_name.split()) if body.full_name else None
    svc.users.update_user(user_id, body.role, body.department_ids, can_publish, name)
    if body.role is not None and body.role.value != user["role"]:
        svc.sessions.revoke_user(user_id)           # a new role takes effect on the next sign-in (and MFA rules with it)
    from ...knowledge.vault_sync import queue_refresh_for_user
    queue_refresh_for_user(svc, user_id, actor.user_id)              # their Obsidian view follows their new access
    audit.record(svc.ops, audit.PERMISSION_CHANGE, actor.user_id, actor.employee_id, action="user_updated", user=user_id,
                 role=body.role.value if body.role else None, can_publish=body.can_publish,
                 department_ids=_uuid_list(body.department_ids) if body.department_ids is not None else None)
    return {"id": str(user_id)}


@router.post("/users/{user_id}/status")
def change_status(user_id: UUID, body: StatusChange, actor: Principal = Depends(require(P.MANAGE_USERS)),
                  svc: Services = Depends(get_services)):
    """§5 FR-AUTH-05: suspend / deactivate / reactivate. Leaving Active revokes every session immediately."""
    if user_id == actor.user_id:
        raise HTTPException(403, "you cannot change the state of your own account")
    user = svc.users.get(user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    if body.status not in ADMIN_STATE_EDGES.get(user["account_status"], set()):
        raise HTTPException(409, f"an account that is {user['account_status']} cannot become {body.status} here")
    prev = svc.users.set_status(user_id, body.status, actor.user_id, body.note, expect={user["account_status"]})
    if prev is None:
        raise HTTPException(409, "the account changed meanwhile; reload and try again")
    revoked = svc.sessions.revoke_user(user_id) if body.status != ACTIVE else 0
    from ...knowledge.vault_sync import queue_refresh_for_user
    queue_refresh_for_user(svc, user_id, actor.user_id)              # suspended / deactivated: their Obsidian view is emptied
    audit.record(svc.ops, audit.PERMISSION_CHANGE, actor.user_id, actor.employee_id, action="account_status", user=user_id,
                 from_status=prev, to_status=body.status, note=body.note, sessions_revoked=revoked)
    return {"id": str(user_id), "account_status": body.status, "sessions_revoked": revoked}


@router.post("/users/{user_id}/mfa-reset")
def reset_mfa(user_id: UUID, actor: Principal = Depends(require(P.MANAGE_USERS)), svc: Services = Depends(get_services)):
    """For a lost phone: the person sets up two-step sign-in again at the next sign-in."""
    if svc.users.get(user_id) is None:
        raise HTTPException(404, "user not found")
    svc.users.set_mfa(user_id, None, enabled=False)
    svc.sessions.revoke_user(user_id)
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="mfa_reset", user=user_id)
    return {"id": str(user_id)}


class BulkDepartments(BaseModel):
    user_ids: list[UUID] = Field(min_length=1, max_length=1000)
    add: list[UUID] = []
    remove: list[UUID] = []


@router.post("/users/bulk-departments")
def bulk_departments(body: BulkDepartments, actor: Principal = Depends(require(P.MANAGE_USERS)),
                     svc: Services = Depends(get_services)):
    """Give many people (or take away) access to departments in one step."""
    if not body.add and not body.remove:
        raise HTTPException(422, "choose departments to add or remove")
    _check_departments(svc, body.add + body.remove)
    n = svc.users.bulk_departments(body.user_ids, body.add, body.remove)
    audit.record(svc.ops, audit.PERMISSION_CHANGE, actor.user_id, actor.employee_id, bulk_users=n,
                 added=_uuid_list(body.add), removed=_uuid_list(body.remove))
    return {"updated": n}


# ---- access requests (§5 FR-AUTH-04, §7 Access requests) ----
class Approval(BaseModel):
    role: Role = Role.EMPLOYEE
    department_ids: list[UUID] = Field(min_length=1)
    can_publish: bool = False
    note: Optional[str] = Field(default=None, max_length=500)


class Rejection(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


@router.get("/access-requests")
def access_requests(_: Principal = Depends(require(P.MANAGE_USERS)), svc: Services = Depends(get_services)):
    out = []
    for r in svc.users.pending_requests():
        rid = r["requested_department_id"]
        out.append({**r, "id": str(r["id"]), "requested_department_id": str(rid) if rid else None,
                    "email_verified": r["email_verified_at"] is not None})
    return {"requests": out}


def _pending(svc: Services, user_id: UUID) -> dict:
    user = svc.users.get(user_id)
    if user is None or user["account_status"] != "pending":
        raise HTTPException(404, "request not found (it may already be decided)")
    return user


@router.post("/access-requests/{user_id}/approve")
def approve_request(user_id: UUID, body: Approval, p: Principal = Depends(require(P.MANAGE_USERS)),
                    svc: Services = Depends(get_services)):
    user = _pending(svc, user_id)
    if not user.get("email_verified_at"):           # §13 AT-01: verify email -> Pending -> admin approves
        raise HTTPException(409, "this person has not verified their email yet")
    _check_departments(svc, body.department_ids)
    if not svc.users.decide_request(user_id, True, body.role, body.department_ids, p.user_id, body.note):
        raise HTTPException(409, "this request was already decided")
    if body.can_publish and body.role is not Role.EMPLOYEE:
        svc.users.update_user(user_id, can_publish=True)
    audit.record(svc.ops, audit.PERMISSION_CHANGE, p.user_id, p.employee_id, action="signup_approved", user=user_id,
                 role=body.role.value, department_ids=_uuid_list(body.department_ids), note=body.note)
    send_safely(svc.mailer, user["email"], *decision_email(user["full_name"], True, svc.settings.public_url))
    return {"approved": True}


@router.post("/access-requests/{user_id}/reject")
def reject_request(user_id: UUID, body: Rejection = Rejection(), p: Principal = Depends(require(P.MANAGE_USERS)),
                   svc: Services = Depends(get_services)):
    user = _pending(svc, user_id)
    if not svc.users.decide_request(user_id, False, None, [], p.user_id, body.note):
        raise HTTPException(409, "this request was already decided")
    svc.sessions.revoke_user(user_id)
    audit.record(svc.ops, audit.PERMISSION_CHANGE, p.user_id, p.employee_id, action="signup_rejected", user=user_id, note=body.note)
    send_safely(svc.mailer, user["email"], *decision_email(user["full_name"], False, svc.settings.public_url))
    return {"rejected": True}


# ---- departments (§7 Departments: create/edit/disable; members, reviewers) ----
class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    status: Optional[Literal["active", "archived"]] = None
    description: Optional[str] = Field(default=None, max_length=300)
    reviewer_ids: Optional[list[UUID]] = None


def _dept_view(d: dict) -> dict:
    return {"id": str(d["id"]), "name": d["name"], "status": d["status"], "description": d.get("description"),
            "reviewer_ids": _uuid_list(d.get("reviewer_ids") or []), "member_count": d.get("member_count", 0)}


@public.get("/departments")
def department_names(p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    """Names of active departments (labels only; what a person may search is `scope` in /v1/auth/me)."""
    return {"departments": [{"id": str(d["id"]), "name": d["name"], "status": d["status"]}
                            for d in svc.users.list_departments(include_archived=False)]}


@router.get("/departments")
def list_departments(_: Principal = Depends(require(P.MANAGE_DEPARTMENTS)), svc: Services = Depends(get_services)):
    return {"departments": [_dept_view(d) for d in svc.users.list_departments()]}


@router.get("/departments/{dept_id}/members")
def department_members(dept_id: UUID, _: Principal = Depends(require(P.MANAGE_DEPARTMENTS)), svc: Services = Depends(get_services)):
    return {"members": [{**m, "id": str(m["id"])} for m in svc.users.department_members(dept_id)]}


@router.post("/departments", status_code=201)
def create_department(body: DepartmentCreate, actor: Principal = Depends(require(P.MANAGE_DEPARTMENTS)),
                      svc: Services = Depends(get_services)):
    name = " ".join(body.name.split())
    if svc.users.department_by_name(name):
        raise HTTPException(409, "a department with this name already exists")
    did = svc.users.create_department(name, body.description)
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="create_department", name=name)
    return {"id": str(did)}


@router.patch("/departments/{dept_id}")
def update_department(dept_id: UUID, body: DepartmentUpdate, actor: Principal = Depends(require(P.MANAGE_DEPARTMENTS)),
                      svc: Services = Depends(get_services)):
    if body.reviewer_ids:
        for uid in body.reviewer_ids:
            u = svc.users.get(uid)
            if not u or u["account_status"] != "active" or u["role"] == Role.EMPLOYEE.value:
                raise HTTPException(422, "reviewers must be active people with a reviewer or admin role")
    svc.users.update_department(dept_id, " ".join(body.name.split()) if body.name else None, body.status, body.description,
                                body.reviewer_ids)
    kind = audit.ARCHIVE_EVENT if body.status == "archived" else audit.PERMISSION_CHANGE
    audit.record(svc.ops, kind, actor.user_id, actor.employee_id, action="update_department", department=dept_id,
                 name=body.name, status=body.status,
                 reviewer_ids=_uuid_list(body.reviewer_ids) if body.reviewer_ids is not None else None)
    return {"id": str(dept_id)}


# ---- API keys for internal apps (§7 API keys: masked, revocable, scoped; plaintext shown once) ----
LIFETIMES = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "1w": timedelta(weeks=1),
             "1m": timedelta(days=30), "1y": timedelta(days=365), "never": None}


class ApiKeyCreate(BaseModel):
    name: str                                # a label for admins; it is NOT part of the key
    permissions: list[str]
    department_ids: list[UUID] = []          # empty = all departments the acting user can see
    expires_in: Literal["1h", "24h", "1w", "1m", "1y", "never"] = "never"    # owner decision: lifetime, not per-minute limits
    rate_limit_per_minute: Optional[int] = None


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


# ---- jobs and reindex (§7 System: indexing jobs) ----
@router.get("/jobs")
def list_jobs(_: Principal = Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    return {"jobs": svc.ops.list_jobs()}


@router.get("/jobs/{job_id}")
def get_job(job_id: UUID, _: Principal = Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    j = svc.ops.get_job(job_id)
    if j is None:
        raise HTTPException(404, "job not found")
    return j


@router.post("/reindex", status_code=202)
def reindex(actor: Principal = Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    """Rebuild every chunk, e.g. after changing the embedding model."""
    audit.record(svc.ops, audit.MODEL_CHANGE, actor.user_id, actor.employee_id, action="reindex",
                 embedding_model=svc.embedder.name)
    return {"job_id": str(enqueue(svc, "reindex", {}, actor.user_id))}
