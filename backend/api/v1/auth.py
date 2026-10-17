"""Authentication and accounts — PRD §5 (FR-AUTH-01..07).

Sign-in creates a server-side session sent as an HttpOnly cookie (FR-AUTH-06); suspension or rejection revokes it at once
(FR-AUTH-05). Self-registered accounts start Pending and can do nothing until an administrator approves them (FR-AUTH-03)."""
from __future__ import annotations

import base64
import io
import re
from typing import Optional
from uuid import UUID

import segno
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ...analytics import audit
from ...auth.security import (_DUMMY_HASH, LoginThrottle, SlidingWindowLimiter, decrypt_secret, encrypt_secret, hash_password,
                              needs_rehash, new_totp_secret, password_problem, totp_uri, verify_password, verify_totp)
from ...learning.feedback import style_hints
from ...notifications.mail import reset_email, send_safely, verification_email
from ...permissions.access import Principal
from ...permissions.roles import ROLE_LABELS, Role, permissions_of
from ..deps import (CSRF_COOKIE, SESSION_COOKIE, SessionInfo, current_principal, current_session, get_services,
                    mfa_required)
from ..services import Services

router = APIRouter(prefix="/v1/auth", tags=["auth"])
throttle = LoginThrottle()

# Messages for states other than Active (FR-AUTH-03/05). Shown only after the right password, so they reveal nothing.
STATE_MESSAGES = {
    "pending": "Your account is waiting for approval by an administrator. You can sign in once it is approved.",
    "rejected": "Your account request was not approved. Please contact your administrator.",
    "suspended": "Your account is suspended. Please contact your administrator.",
    "deactivated": "Your account is no longer active. Please contact your administrator.",
}


def _client(request: Request) -> tuple[str, str]:
    return (request.client.host if request.client else "unknown"), request.headers.get("user-agent", "")


def _set_session_cookies(response: Response, svc: Services, token: str, csrf: str) -> None:
    secure, ttl = svc.settings.secure_cookies, svc.settings.session_ttl_seconds
    response.set_cookie(SESSION_COOKIE, token, max_age=ttl, httponly=True, secure=secure, samesite="lax", path="/")
    response.set_cookie(CSRF_COOKIE, csrf, max_age=ttl, httponly=False, secure=secure, samesite="lax", path="/")


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


class LoginRequest(BaseModel):
    identifier: str = Field(max_length=200)        # email or username
    password: str = Field(max_length=200)


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, svc: Services = Depends(get_services)):
    ident = body.identifier.strip()
    if throttle.blocked(ident):
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")
    user = svc.users.get_by_login(ident)
    ok = verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)   # same work whether or not it exists
    if not user or not ok:
        throttle.failure(ident)
        audit.record(svc.ops, audit.FAILED_AUTHENTICATION, None, ident)
        raise HTTPException(401, "invalid credentials")
    state = user["account_status"]
    if state != "active":
        audit.record(svc.ops, audit.FAILED_AUTHENTICATION, user["id"], user["employee_id"], reason=state)
        detail = STATE_MESSAGES[state]
        if state == "pending" and not user.get("email_verified_at"):
            detail = "Please verify your email first: open the link we sent you. Then an administrator can approve your account."
        raise HTTPException(403, detail)
    throttle.success(ident)
    if needs_rehash(user["password_hash"]):                 # legacy scrypt -> Argon2id (FR-AUTH-06)
        svc.users.set_password_hash(user["id"], hash_password(body.password))
    ip, ua = _client(request)
    needs_mfa = mfa_required(user, svc)
    token, csrf = svc.sessions.create(user["id"], svc.settings.session_ttl_seconds, mfa_passed=not needs_mfa, ip=ip, user_agent=ua)
    _set_session_cookies(response, svc, token, csrf)
    svc.users.record_login(user["id"])
    audit.record(svc.ops, audit.USER_LOGIN, user["id"], user["employee_id"])
    mfa = "none" if not needs_mfa else ("verify" if user.get("mfa_enabled_at") else "setup")
    return {"status": "ok", "mfa": mfa, "csrf_token": csrf}


@router.post("/logout")
def logout(response: Response, info: SessionInfo = Depends(current_session), svc: Services = Depends(get_services)):
    svc.sessions.revoke(info.session["id"])
    _clear_session_cookies(response)
    return {"status": "signed_out"}


# ---- admin MFA (FR-AUTH-06): TOTP from an authenticator app ----
class MfaCode(BaseModel):
    code: str = Field(max_length=12)


def _mfa_key(svc: Services) -> str:
    return svc.settings.field_encryption_key


@router.get("/mfa/setup")
def mfa_setup(info: SessionInfo = Depends(current_session), svc: Services = Depends(get_services)):
    """A new secret to add to an authenticator app. Not available once MFA is on (resetting it is an admin action)."""
    user = info.user
    if user.get("mfa_enabled_at"):
        raise HTTPException(409, "two-step sign-in is already set up")
    secret = new_totp_secret()
    svc.users.set_mfa(user["id"], encrypt_secret(secret, _mfa_key(svc)), enabled=False)
    uri = totp_uri(secret, user["email"])
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=5, border=2)
    return {"secret": secret, "otpauth_uri": uri,
            "qr_svg": "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()}


def _check_code(info: SessionInfo, svc: Services, code: str, secret_enc: Optional[str]) -> None:
    key = f"mfa:{info.user['id']}"
    if throttle.blocked(key):
        raise HTTPException(429, "Too many wrong codes. Please wait 15 minutes and try again.")
    secret = decrypt_secret(secret_enc or "", _mfa_key(svc))
    if not secret or not verify_totp(secret, code):
        throttle.failure(key)
        audit.record(svc.ops, audit.FAILED_AUTHENTICATION, info.user["id"], info.user["employee_id"], reason="mfa")
        raise HTTPException(401, "That code is not correct. Check the time on your phone and try again.")
    throttle.success(key)
    svc.sessions.mark_mfa_passed(info.session["id"])


@router.post("/mfa/enable")
def mfa_enable(body: MfaCode, info: SessionInfo = Depends(current_session), svc: Services = Depends(get_services)):
    user = svc.users.get(info.user["id"])                 # the secret was saved by /mfa/setup in this session
    if user.get("mfa_enabled_at"):
        raise HTTPException(409, "two-step sign-in is already set up")
    _check_code(info, svc, body.code, user.get("mfa_secret_enc"))
    svc.users.set_mfa(user["id"], user["mfa_secret_enc"], enabled=True)
    audit.record(svc.ops, audit.ADMIN_ACTION, user["id"], user["employee_id"], action="mfa_enabled")
    return {"mfa": "passed"}


@router.post("/mfa/verify")
def mfa_verify(body: MfaCode, info: SessionInfo = Depends(current_session), svc: Services = Depends(get_services)):
    if not info.user.get("mfa_enabled_at"):
        raise HTTPException(409, "two-step sign-in is not set up yet")
    _check_code(info, svc, body.code, info.user.get("mfa_secret_enc"))
    return {"mfa": "passed"}


# ---- self sign-up (FR-AUTH-01): the person picks a username and password; an administrator approves (FR-AUTH-04) ----
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,29}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9 ()-]{7,20}$")
signup_limiter = SlidingWindowLimiter(window_seconds=3600)       # accounts actually requested
attempt_limiter = SlidingWindowLimiter(window_seconds=3600)      # every try, so usernames cannot be probed without limit
mail_limiter = SlidingWindowLimiter(window_seconds=3600)         # verification / reset emails per address
SIGNUPS_PER_HOUR, ATTEMPTS_PER_HOUR, MAILS_PER_HOUR = 5, 30, 5   # implementation necessity against abuse (docs/PRD_GAPS.md)


class Registration(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    username: str = Field(min_length=3, max_length=30)
    email: str = Field(max_length=120)
    password: str = Field(min_length=8, max_length=200)
    department_id: UUID                          # FR-AUTH-01 "requested department" (required)
    phone: Optional[str] = Field(default=None, max_length=30)      # FR-AUTH-01 optional


@router.get("/signup-options")
def signup_options(svc: Services = Depends(get_services)):
    """Public: department names for the sign-up form (names only, no people, no knowledge)."""
    return {"departments": [{"id": str(d["id"]), "name": d["name"]} for d in svc.users.list_departments(include_archived=False)]}


def _send_verification(svc: Services, user_id: UUID, name: str, email: str) -> None:
    token = svc.one_time.issue(user_id, "verify_email", svc.settings.one_time_link_ttl_seconds)
    send_safely(svc.mailer, email, *verification_email(name, f"{svc.settings.public_url}/#/verify?token={token}"))


@router.post("/register", status_code=201)
def register(body: Registration, request: Request, svc: Services = Depends(get_services)):
    ip, _ = _client(request)
    if not attempt_limiter.allow(ip, ATTEMPTS_PER_HOUR):
        raise HTTPException(429, "Too many sign-up requests. Please try again later.")
    username, email = body.username.strip().lower(), body.email.strip().lower()
    name = " ".join(body.full_name.split())
    phone = " ".join((body.phone or "").split()) or None
    if not USERNAME_RE.match(username):
        raise HTTPException(422, "The username must be 3-30 characters: lowercase letters, numbers, dot, dash or underscore.")
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    if len(name) < 2:
        raise HTTPException(422, "Enter your full name.")
    if phone and not PHONE_RE.match(phone):
        raise HTTPException(422, "Enter a valid phone number or leave it empty.")
    problem = password_problem(body.password, username, email.split("@")[0], name)
    if problem:
        raise HTTPException(422, problem)
    if body.department_id not in svc.users.all_department_ids():
        raise HTTPException(422, "Choose the department you work in.")
    if svc.users.username_or_email_taken(username, email):
        raise HTTPException(409, "That username or email is already taken. Choose another, or sign in if it is yours.")
    if not signup_limiter.allow(ip, SIGNUPS_PER_HOUR):
        raise HTTPException(429, "Too many accounts were requested from this address. Please try again later.")
    uid = svc.users.create_pending_user(username, email, name, hash_password(body.password), body.department_id, phone)
    audit.record(svc.ops, audit.PERMISSION_CHANGE, uid, username, action="signup_requested")
    _send_verification(svc, uid, name, email)
    return {"status": "pending", "email_verification": "sent"}


class TokenBody(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/verify-email")
def verify_email(body: TokenBody, svc: Services = Depends(get_services)):
    uid = svc.one_time.consume(body.token, "verify_email")
    if uid is None:
        raise HTTPException(400, "This link is not valid any more. Ask for a new one from the sign-in page.")
    svc.users.mark_email_verified(uid)
    user = svc.users.get(uid)
    audit.record(svc.ops, audit.ADMIN_ACTION, uid, user["employee_id"], action="email_verified")
    return {"verified": True, "account_status": user["account_status"]}


class EmailBody(BaseModel):
    identifier: str = Field(max_length=200)        # email or username


@router.post("/verify-email/resend", status_code=202)
def resend_verification(body: EmailBody, request: Request, svc: Services = Depends(get_services)):
    """Always 202, so it never reveals whether an account exists (PRD §10 account enumeration)."""
    ip, _ = _client(request)
    user = svc.users.get_by_login(body.identifier.strip())
    if user and not user.get("email_verified_at") and mail_limiter.allow(f"{ip}:{user['id']}", MAILS_PER_HOUR):
        _send_verification(svc, user["id"], user["full_name"], user["email"])
    return {"status": "if the account exists and is not verified, a new link was sent"}


@router.post("/password-reset", status_code=202)
def password_reset_request(body: EmailBody, request: Request, svc: Services = Depends(get_services)):
    """FR-AUTH-06 password reset. Always 202 (no account enumeration). Only Active accounts get a link."""
    ip, _ = _client(request)
    user = svc.users.get_by_login(body.identifier.strip())
    if user and user["account_status"] == "active" and mail_limiter.allow(f"{ip}:{user['id']}", MAILS_PER_HOUR):
        token = svc.one_time.issue(user["id"], "reset_password", svc.settings.one_time_link_ttl_seconds)
        send_safely(svc.mailer, user["email"], *reset_email(user["full_name"], f"{svc.settings.public_url}/#/reset?token={token}"))
    return {"status": "if the account exists, a reset link was sent"}


class ResetConfirm(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/password-reset/confirm")
def password_reset_confirm(body: ResetConfirm, svc: Services = Depends(get_services)):
    uid = svc.one_time.consume(body.token, "reset_password")
    user = svc.users.get(uid) if uid else None
    if not user or user["account_status"] != "active":
        raise HTTPException(400, "This link is not valid any more. Ask for a new one.")
    problem = password_problem(body.new_password, user["employee_id"], user["email"].split("@")[0], user["full_name"])
    if problem:
        raise HTTPException(422, problem)
    svc.users.set_password_hash(uid, hash_password(body.new_password))
    svc.sessions.revoke_user(uid)                       # every device signs in again with the new password
    audit.record(svc.ops, audit.ADMIN_ACTION, uid, user["employee_id"], action="password_reset")
    return {"changed": True}


STYLES = ("concise", "balanced", "detailed")
TONES = ("professional", "friendly", "direct")
LANGUAGES = ("auto", "english", "urdu", "roman_urdu")
AVATAR_PREFIXES = ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")
MAX_AVATAR_CHARS = 300_000          # a 256 px photo is ~30-60 KB; bounds what one profile can store


def clean_preferences(raw: dict | None) -> dict:
    """Only known keys with known values; free text is trimmed and length-limited. Used when saving AND when reading, so a
    hand-edited row can never put anything else into a prompt."""
    raw = raw or {}
    pick = lambda key, allowed, default: raw.get(key) if raw.get(key) in allowed else default
    text = lambda key, n: " ".join(str(raw.get(key) or "").split())[:n]
    return {"answer_style": pick("answer_style", STYLES, "balanced"), "tone": pick("tone", TONES, "professional"),
            "language": pick("language", LANGUAGES, "auto"), "about_me": text("about_me", 500), "instructions": text("instructions", 500),
            "learn": raw.get("learn") is not False}                     # learn from my 👍/👎 (default on)


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=80)
    avatar: Optional[str] = None            # data URL of a png / jpeg / webp image; "" removes the picture


class PreferencesUpdate(BaseModel):
    answer_style: str = "balanced"
    tone: str = "professional"
    language: str = "auto"
    about_me: str = Field(default="", max_length=500)
    instructions: str = Field(default="", max_length=500)
    learn: bool = True


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


def _me(p: Principal, svc: Services) -> dict:
    """PRD §5 FR-AUTH-07: name, department(s), effective access scope and account settings."""
    user = svc.users.get(p.user_id)
    depts = {d["id"]: d for d in svc.users.list_departments()}
    active = {d for d, row in depts.items() if row["status"] == "active"}
    scope = active if p.all_departments else (p.department_ids & active)
    return {"user_id": str(p.user_id), "employee_id": p.employee_id, "role": p.role.value, "role_label": ROLE_LABELS[p.role],
            "permissions": permissions_of(p.role), "can_publish": p.can_publish,
            "account_status": user["account_status"], "email_verified": bool(user.get("email_verified_at")),
            "mfa_enabled": bool(user.get("mfa_enabled_at")),
            "full_name": user["full_name"], "email": user["email"], "phone": user.get("phone"), "avatar": user.get("avatar"),
            "preferences": clean_preferences(user.get("preferences")),
            "department_ids": [str(d) for d in p.department_ids],
            "departments": [{"id": str(d), "name": depts[d]["name"]} for d in p.department_ids if d in depts],
            # §6 FR-CHAT-06 / §4.2: the scopes this person may search; "Company Wide" only when it is really all of them
            "scope": [{"id": str(d), "name": depts[d]["name"]} for d in sorted(scope, key=lambda x: depts[x]["name"])],
            "company_wide": bool(active) and scope == active,
            "reviews_department_ids": [str(d) for d in p.managed_department_ids]}


@router.get("/me")
def me(p: Principal = Depends(current_principal), svc: Services = Depends(get_services)):
    return _me(p, svc)


@router.get("/session")
def session_state(info: SessionInfo = Depends(current_session), svc: Services = Depends(get_services)):
    """What the app must show before the main screen: nothing, or the two-step sign-in (setup or code)."""
    need = mfa_required(info.user, svc) and not info.session["mfa_passed"]
    return {"mfa": "none" if not need else ("verify" if info.user.get("mfa_enabled_at") else "setup"),
            "full_name": info.user["full_name"], "email": info.user["email"]}


@router.get("/status-history")
def my_status_history(p: Principal = Depends(current_principal), svc: Services = Depends(get_services)):
    """FR-AUTH-07 / §3 Employee: "view own account status"."""
    return {"history": [{**h, "actor": h["actor"]} for h in svc.users.status_history(p.user_id)]}


@router.patch("/profile")
def update_profile(body: ProfileUpdate, p: Principal = Depends(current_principal), svc: Services = Depends(get_services)):
    name = " ".join(body.full_name.split()) if body.full_name is not None else None
    if name is not None and not name:
        raise HTTPException(422, "name cannot be empty")
    avatar, clear = None, False
    if body.avatar == "":
        clear = True
    elif body.avatar is not None:
        if not body.avatar.startswith(AVATAR_PREFIXES) or len(body.avatar) > MAX_AVATAR_CHARS:
            raise HTTPException(422, "the picture must be a PNG, JPEG or WebP image under about 200 KB")
        try:
            base64.b64decode(body.avatar.split(",", 1)[1], validate=True)
        except Exception:
            raise HTTPException(422, "the picture could not be read")
        avatar = body.avatar
    svc.users.update_profile(p.user_id, name, avatar, clear)
    return _me(p, svc)


@router.put("/preferences")
def save_preferences(body: PreferencesUpdate, p: Principal = Depends(current_principal), svc: Services = Depends(get_services)):
    prefs = clean_preferences(body.model_dump())
    svc.users.set_preferences(p.user_id, prefs)
    return prefs


def learned_hints(svc, user_id, user=None) -> list[str]:
    """Style patterns found in this person's own ratings (backend/learning/feedback.py). Empty when learning is off or too few ratings."""
    if not getattr(svc.settings, "feedback_learning", False) or not hasattr(svc.ops, "rated_answers"):
        return []
    user = user or svc.users.get(user_id) or {}
    since = max([t for t in (user.get("learning_reset_at"), svc.ops.learning_since()) if t], default=None)
    return style_hints(svc.ops.rated_answers(user_id, since))


@router.get("/learned")
def learned(p: Principal = Depends(current_principal), svc: Services = Depends(get_services)):
    user = svc.users.get(p.user_id) or {}
    since = max([t for t in (user.get("learning_reset_at"), svc.ops.learning_since()) if t], default=None)
    rated = svc.ops.rated_answers(p.user_id, since)
    return {"enabled": bool(svc.settings.feedback_learning and clean_preferences(user.get("preferences"))["learn"]),
            "hints": style_hints(rated), "liked": sum(r["helpful"] for r in rated), "disliked": sum(not r["helpful"] for r in rated)}


@router.post("/learned/reset")
def forget_learned(p: Principal = Depends(current_principal), svc: Services = Depends(get_services)):
    svc.ops.reset_user_learning(p.user_id)
    return {"reset": True}


@router.post("/password")
def change_password(body: PasswordChange, p: Principal = Depends(current_principal), info: SessionInfo = Depends(current_session),
                    svc: Services = Depends(get_services)):
    key = f"pw:{p.user_id}"
    if throttle.blocked(key):
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")
    user = svc.users.get(p.user_id)
    if not verify_password(body.current_password, user["password_hash"]):
        throttle.failure(key)
        raise HTTPException(403, "Your current password is not correct.")
    if body.new_password == body.current_password:
        raise HTTPException(422, "Choose a password different from the current one.")
    problem = password_problem(body.new_password, user["employee_id"], user["email"].split("@")[0], user["full_name"])
    if problem:
        raise HTTPException(422, problem)
    throttle.success(key)
    svc.users.set_password_hash(p.user_id, hash_password(body.new_password))
    svc.sessions.revoke_user(p.user_id, except_session=info.session["id"])      # other devices sign in again
    audit.record(svc.ops, audit.ADMIN_ACTION, p.user_id, p.employee_id, action="password_changed")
    return {"changed": True}
