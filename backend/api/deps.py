"""Authentication & authorization dependencies — PRD §3 (deny by default, checked on every call), §5 FR-AUTH-03/05/06.

A person is authenticated by a server-side session: the HttpOnly `qb_session` cookie (browsers) or the same token as a
Bearer header (non-browser clients). Only Active accounts pass (§5 FR-AUTH-03/05); roles in MFA_ROLES must have passed MFA
in this session (§5 FR-AUTH-06); cookie-authenticated writes need the session's CSRF token in `X-CSRF-Token`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from ..auth.security import hash_api_key
from ..permissions.access import Principal
from ..permissions.roles import MFA_ROLES, P, Role, can
from .services import Services

# PRD §10 says keys need scoped access but not its vocabulary; endpoint names are used (docs/PRD_GAPS.md).
KEY_PERMISSIONS = {"ask", "search", "documents", "sales_memory", "feedback"}
SESSION_COOKIE, CSRF_COOKIE, CSRF_HEADER = "qb_session", "qb_csrf", "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


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


@dataclass
class SessionInfo:
    session: dict
    user: dict
    via_cookie: bool


def _bearer(authorization: Optional[str]) -> Optional[str]:
    return authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else None


def mfa_required(user: dict, svc: Services) -> bool:
    return bool(svc.settings.admin_mfa_required) and Role(user["role"]) in MFA_ROLES


def current_session(request: Request, authorization: Optional[str] = Header(default=None),
                    svc: Services = Depends(get_services)) -> SessionInfo:
    """A live session of an Active account. MFA is NOT checked here (the MFA endpoints use this directly)."""
    bearer = _bearer(authorization)
    token = bearer or request.cookies.get(SESSION_COOKIE)
    sess = svc.sessions.lookup(token) if token else None
    user = svc.users.get(sess["user_id"]) if sess else None
    if not sess or not user or user["account_status"] != "active":
        if sess:                                   # suspended / deactivated while signed in: end the session now
            svc.sessions.revoke(sess["id"])
        raise HTTPException(401, "authentication required")
    via_cookie = bearer is None
    if via_cookie and request.method not in SAFE_METHODS:
        if request.headers.get(CSRF_HEADER) != sess["csrf_token"]:
            raise HTTPException(403, "missing or invalid CSRF token; reload the page and try again")
    return SessionInfo(sess, user, via_cookie)


def current_principal(info: SessionInfo = Depends(current_session), svc: Services = Depends(get_services)) -> Principal:
    if mfa_required(info.user, svc) and not info.session["mfa_passed"]:
        raise HTTPException(401, "mfa_required")
    return svc.users.principal(info.user)


def require(permission: P):
    def dep(principal: Principal = Depends(current_principal)) -> Principal:
        if not can(principal.role, permission):
            raise HTTPException(403, f"your role cannot do this ({permission.value})")
        return principal
    return dep


def api_caller(key_permission: str, user_id_field: str = "user_id"):
    """Employee (session) OR internal app (X-API-Key + employee `user_id` in the body)."""
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
        return Caller(principal=current_principal(current_session(request, authorization, svc), svc))
    return dep


def resolve_caller(caller: Caller, user_id: Optional[str], svc: Services) -> Caller:
    """API-key calls act as the employee named in the body (PRD §38 `user_id`); without one, as the person who
    created the key (so a key works on its own, like an LLM provider key)."""
    if caller.key is None:
        return caller
    user = svc.users.get_by_employee_id(user_id) if user_id else svc.users.get(caller.key.get("created_by"))
    if not user or user.get("account_status", "active") != "active":         # §5 FR-AUTH-05: only Active accounts
        raise HTTPException(403, "unknown user_id" if user_id else "the user who created this key no longer exists")
    return Caller(principal=svc.users.principal(user), key=caller.key)
