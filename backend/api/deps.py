"""Authentication & authorization dependencies — PRD §11.3 (identity, role, department), §40, §41, §42."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from ..auth.security import hash_api_key, read_token
from ..permissions.access import Principal
from ..permissions.roles import P, can
from .services import Services

# PRD §40 says keys have "Permissions" but not their vocabulary; endpoint names are used (docs/PRD_GAPS.md).
KEY_PERMISSIONS = {"ask", "search", "documents", "sales_memory", "feedback"}


def get_services(request: Request) -> Services:
    return request.app.state.services


@dataclass
class Caller:
    principal: Principal
    key: Optional[dict] = None          # set when an internal app (API key) is calling on behalf of a user

    @property
    def key_department_ids(self):
        """None = no restriction (an empty list on the key means "all departments")."""
        allowed = self.key.get("allowed_department_ids") if self.key else None
        return frozenset(allowed) if allowed else None


def _bearer(authorization: Optional[str]) -> Optional[str]:
    return authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else None


def current_principal(authorization: Optional[str] = Header(default=None),
                      svc: Services = Depends(get_services)) -> Principal:
    token = _bearer(authorization)
    uid = read_token(token, svc.settings.session_secret) if token else None
    user = svc.users.get(uid) if uid else None
    if not user or not user["is_active"]:
        raise HTTPException(401, "authentication required")
    return svc.users.principal(user)


def require(permission: P):
    def dep(principal: Principal = Depends(current_principal)) -> Principal:
        if not can(principal.role, permission):
            raise HTTPException(403, f"your role cannot do this ({permission.value})")
        return principal
    return dep


def api_caller(key_permission: str, user_id_field: str = "user_id"):
    """Employee (Bearer token) OR internal app (X-API-Key + employee `user_id` in the body, PRD §38)."""
    def dep(request: Request, authorization: Optional[str] = Header(default=None),
            x_api_key: Optional[str] = Header(default=None), svc: Services = Depends(get_services)) -> Caller:
        if x_api_key:
            key = svc.ops.api_key_by_hash(hash_api_key(x_api_key))
            if not key:
                raise HTTPException(401, "invalid API key")
            if key.get("status", "active") != "active":
                raise HTTPException(401, "this API key has been revoked")
            expires = key.get("expires_at")
            if expires and expires <= datetime.now(timezone.utc):
                raise HTTPException(401, "this API key has expired")
            if key_permission not in key["permissions"]:
                raise HTTPException(403, f"this API key has no '{key_permission}' permission")
            limit = key.get("rate_limit_per_minute")          # optional: no limit unless one was set
            if limit and not svc.limiter.allow(str(key["id"]), limit):
                raise HTTPException(429, "rate limit exceeded")
            svc.ops.touch_api_key(key["id"])
            return Caller(principal=None, key=key)          # bound to an employee by `resolve_caller` (body user_id)
        return Caller(principal=current_principal(authorization, svc))
    return dep


def resolve_caller(caller: Caller, user_id: Optional[str], svc: Services) -> Caller:
    """API-key calls act as the employee named in the body (PRD §38 `user_id`); without one, as the person who
    created the key (so a key works on its own, like an LLM provider key)."""
    if caller.key is None:
        return caller
    user = svc.users.get_by_employee_id(user_id) if user_id else svc.users.get(caller.key.get("created_by"))
    if not user:
        raise HTTPException(403, "unknown user_id" if user_id else "the user who created this key no longer exists")
    return Caller(principal=svc.users.principal(user), key=caller.key)
