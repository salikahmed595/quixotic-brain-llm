"""Authentication — PRD §41 (V1: email or employee ID + password)."""
from __future__ import annotations

import base64
import re
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ...analytics import audit
from ...learning.feedback import style_hints
from ...auth.security import _DUMMY_HASH, LoginThrottle, SlidingWindowLimiter, hash_password, issue_token, verify_password
from ...permissions.access import Principal
from ..deps import current_principal, get_services
from ..services import Services

router = APIRouter(prefix="/v1/auth", tags=["auth"])
throttle = LoginThrottle()


class LoginRequest(BaseModel):
    identifier: str          # email or employee ID
    password: str


@router.post("/login")
def login(body: LoginRequest, svc: Services = Depends(get_services)):
    ident = body.identifier.strip()
    if throttle.blocked(ident):
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")
    user = svc.users.get_by_login_any(ident)
    ok = verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)   # same work whether or not the account exists
    if not user or not ok:
        throttle.failure(ident)
        audit.record(svc.ops, audit.FAILED_AUTHENTICATION, None, ident)     # §53
        raise HTTPException(401, "invalid credentials")
    # The right password was given, so it is safe to say why an account cannot sign in yet.
    if user["approval_status"] == "pending":
        raise HTTPException(403, "Your account is waiting for approval by an administrator or manager. You can sign in once it is approved.")
    if user["approval_status"] == "rejected":
        raise HTTPException(403, "Your account request was not approved. Please contact your administrator.")
    if not user["is_active"]:
        throttle.failure(ident)
        audit.record(svc.ops, audit.FAILED_AUTHENTICATION, None, ident)
        raise HTTPException(401, "invalid credentials")
    throttle.success(ident)
    audit.record(svc.ops, audit.USER_LOGIN, user["id"], user["employee_id"])
    token = issue_token(user["id"], svc.settings.session_secret, svc.settings.session_ttl_seconds)
    return {"access_token": token, "token_type": "bearer"}


# ---- self sign-up (owner request): the person picks their own username and password; an administrator or manager approves ----
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,29}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
signup_limiter = SlidingWindowLimiter(window_seconds=3600)       # accounts actually requested
attempt_limiter = SlidingWindowLimiter(window_seconds=3600)      # every try, so usernames cannot be probed without limit
SIGNUPS_PER_HOUR, ATTEMPTS_PER_HOUR = 5, 30      # per address; implementation necessity against spam (docs/PRD_GAPS.md)


class Registration(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    username: str = Field(min_length=3, max_length=30)
    email: str = Field(max_length=120)
    password: str = Field(min_length=8, max_length=200)
    department_id: Optional[UUID] = None         # the department they say they work in; the approver decides


@router.get("/signup-options")
def signup_options(svc: Services = Depends(get_services)):
    """Public: department names for the sign-up form (names only, no people, no knowledge)."""
    return {"departments": [{"id": str(d["id"]), "name": d["name"]} for d in svc.users.list_departments() if d["status"] == "active"]}


@router.post("/register", status_code=201)
def register(body: Registration, request: Request, svc: Services = Depends(get_services)):
    ip = request.client.host if request.client else "unknown"
    if not attempt_limiter.allow(ip, ATTEMPTS_PER_HOUR):
        raise HTTPException(429, "Too many sign-up requests. Please try again later.")
    username, email = body.username.strip().lower(), body.email.strip().lower()
    name = " ".join(body.full_name.split())
    if not USERNAME_RE.match(username):
        raise HTTPException(422, "The username must be 3-30 characters: lowercase letters, numbers, dot, dash or underscore.")
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    if len(name) < 2:
        raise HTTPException(422, "Enter your full name.")
    if body.department_id is not None and body.department_id not in svc.users.all_department_ids():
        raise HTTPException(422, "unknown department")
    if svc.users.username_or_email_taken(username, email):
        raise HTTPException(409, "That username or email is already taken. Choose another, or sign in if it is yours.")
    if not signup_limiter.allow(ip, SIGNUPS_PER_HOUR):
        raise HTTPException(429, "Too many accounts were requested from this address. Please try again later.")
    uid = svc.users.create_pending_user(username, email, name, hash_password(body.password), body.department_id)
    audit.record(svc.ops, audit.PERMISSION_CHANGE, uid, username, action="signup_requested")
    return {"status": "pending"}


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
    user = svc.users.get(p.user_id)
    depts = {d["id"]: d for d in svc.users.list_departments()}
    return {"user_id": str(p.user_id), "employee_id": p.employee_id, "role": p.role.value,
            "full_name": user["full_name"], "email": user["email"], "avatar": user.get("avatar"),
            "preferences": clean_preferences(user.get("preferences")),
            "department_ids": [str(d) for d in p.department_ids],
            "departments": [{"id": str(d), "name": depts[d]["name"]} for d in p.department_ids if d in depts]}


@router.get("/me")
def me(p: Principal = Depends(current_principal), svc: Services = Depends(get_services)):
    return _me(p, svc)


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
def change_password(body: PasswordChange, p: Principal = Depends(current_principal), svc: Services = Depends(get_services)):
    key = f"pw:{p.user_id}"
    if throttle.blocked(key):
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")
    user = svc.users.get(p.user_id)
    if not verify_password(body.current_password, user["password_hash"]):
        throttle.failure(key)
        raise HTTPException(403, "Your current password is not correct.")
    if body.new_password == body.current_password:
        raise HTTPException(422, "Choose a password different from the current one.")
    throttle.success(key)
    svc.users.set_password_hash(p.user_id, hash_password(body.new_password))
    audit.record(svc.ops, audit.ADMIN_ACTION, p.user_id, p.employee_id, action="password_changed")
    return {"changed": True}
