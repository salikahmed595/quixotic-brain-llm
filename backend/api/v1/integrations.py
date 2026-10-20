"""Integrations — PRD §9 (Hermes / Telegram / Obsidian knowledge updates), §11 (`POST /integrations/hermes/knowledge-proposals`:
"signed service-to-service request, not a public untrusted write endpoint"), §15 (Hermes has no open-ended permissions).

Hermes reaches this backend only through the quixotic-mcp sidecar, which signs every call with QB_HERMES_SHARED_SECRET:
    X-Quixotic-Timestamp: <unix seconds>      X-Quixotic-Signature: hex(HMAC-SHA256(secret, f"{timestamp}.{raw body}"))
Calls older than 5 minutes or with a bad signature are refused. The person behind a call is the Telegram account the sidecar
names; it must be linked to an active user (§9 step 1), and every proposal still waits for that person's own confirmation tap in
the backend-owned approvals bot, so a model can never act in someone else's name."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from ...analytics import audit
from ...knowledge.service import Draft, KnowledgeError, KnowledgeService, may_review
from ...permissions.access import resolve_department_scope
from ...permissions.roles import P, can
from ..deps import get_services, require
from ..services import Services

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])
admin = APIRouter(prefix="/v1/admin/integrations", tags=["integrations"])
MAX_SKEW = 300


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


async def signed(request: Request, x_quixotic_timestamp: Optional[str] = Header(default=None),
                 x_quixotic_signature: Optional[str] = Header(default=None), svc: Services = Depends(get_services)) -> bytes:
    secret = svc.settings.hermes_shared_secret
    if not secret:
        raise HTTPException(404, "not found")                          # integration not configured: the endpoint does not exist
    body = await request.body()
    try:
        fresh = abs(time.time() - int(x_quixotic_timestamp or "0")) <= MAX_SKEW
    except ValueError:
        fresh = False
    if not fresh or not x_quixotic_signature or not hmac.compare_digest(sign(secret, x_quixotic_timestamp, body), x_quixotic_signature):
        raise HTTPException(401, "bad or expired signature")
    return body


def _person(svc: Services, telegram_user_id: str):
    user = svc.integrations.user_for("telegram", telegram_user_id)
    if user is None:
        raise HTTPException(403, "This Telegram account is not linked to an active Quixotic AI account. Ask an administrator to link it.")
    return user, svc.users.principal(user)


class Who(BaseModel):
    telegram_user_id: str = Field(min_length=1, max_length=32)


@router.post("/hermes/context")
def hermes_context(body: Who, _: bytes = Depends(signed), svc: Services = Depends(get_services)):
    """What the agent needs to ask good questions: the person's departments, the access levels, existing categories."""
    user, p = _person(svc, body.telegram_user_id)
    scope = resolve_department_scope(p, svc.users.all_department_ids())
    names = {d["id"]: d["name"] for d in svc.users.list_departments(include_archived=False)}
    return {"name": user["full_name"], "role": p.role.value, "can_propose": can(p.role, P.PROPOSE_KNOWLEDGE),
            "departments": sorted(names[d] for d in scope if d in names), "sensitivity_levels": sorted(svc.settings.levels_for(p.role.value)),
            "categories": svc.knowledge.categories()}


class SearchIn(Who):
    query: str = Field(min_length=1, max_length=2000)


@router.post("/hermes/search")
def hermes_search(body: SearchIn, _: bytes = Depends(signed), svc: Services = Depends(get_services)):
    """Approved, published knowledge this person may see (§8 filters before ranking), as passages with their source."""
    user, p = _person(svc, body.telegram_user_id)
    scope = resolve_department_scope(p, svc.users.all_department_ids())
    out = svc.search.search(body.query, scope, svc.settings.levels_for(p.role.value))
    return {"results": [{"title": c.title, "section": c.section, "version": c.version, "document_id": str(c.item_id), "text": c.text}
                        for c in out.candidates]}


class ProposalIn(Who):
    message_id: str = Field(min_length=1, max_length=64)               # the Telegram message id: each message writes at most once
    intent: Literal["add_fact", "edit_rule", "replace_policy"]          # §9 step 3 ("ask question" and "report gap" use other tools)
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1, max_length=50_000)                  # the proposed Markdown text (whole document after the change)
    departments: list[str] = Field(min_length=1)
    sensitivity: Optional[str] = None                                   # required for a new document; updates keep the current level
    category: Optional[str] = Field(default=None, max_length=80)
    target_document_id: Optional[UUID] = None                           # for edit_rule / replace_policy
    transcript: Optional[str] = Field(default=None, max_length=8000)    # the voice note as heard (§9 step 2)
    change_note: Optional[str] = Field(default=None, max_length=1000)
    high_impact: bool = False


@router.post("/hermes/knowledge-proposals", status_code=201)
def hermes_proposal(body: ProposalIn, _: bytes = Depends(signed), svc: Services = Depends(get_services)):
    """PRD §11. Creates a proposal that waits for the sender's confirmation in the approvals bot, then for review (§9 steps 4–5)."""
    user, p = _person(svc, body.telegram_user_id)
    if not can(p.role, P.PROPOSE_KNOWLEDGE):
        raise HTTPException(403, "Your role cannot propose knowledge.")
    by_name = {d["name"].lower(): d["id"] for d in svc.users.list_departments(include_archived=False)}
    unknown = [n for n in body.departments if n.lower() not in by_name]
    if unknown:
        raise HTTPException(422, f"Unknown department(s): {', '.join(unknown)}. Ask which department it is for.")
    ks = KnowledgeService(svc)
    ref = f"{body.telegram_user_id}:{body.message_id}"
    try:
        if body.target_document_id:
            item = svc.knowledge.get_item(body.target_document_id)
            if item is None:
                raise HTTPException(404, "document not found")
            d = Draft(title=body.title, body=body.body, department_ids=[by_name[n.lower()] for n in body.departments],
                      sensitivity=body.sensitivity or item["sensitivity"], category=body.category or item["category"],
                      owner_id=item["owner_id"], provenance=item["provenance"] or "Telegram", change_note=body.change_note,
                      high_impact=body.high_impact)
            out = ks.propose_update(p, body.target_document_id, d, source="telegram", source_ref=ref, confirm_first=True,
                                    transcript=body.transcript)
        else:
            if not body.sensitivity:
                raise HTTPException(422, f"Ask who may see it. Access levels: {', '.join(sorted(svc.settings.levels_for(p.role.value)))}")
            d = Draft(title=body.title, body=body.body, department_ids=[by_name[n.lower()] for n in body.departments],
                      sensitivity=body.sensitivity, category=body.category, owner_id=user["id"],
                      provenance=f"Telegram message from {user['full_name']}", change_note=body.change_note, high_impact=body.high_impact)
            out = ks.propose_new(p, d, source="telegram", source_ref=ref, confirm_first=True, transcript=body.transcript)
    except KnowledgeError as e:
        raise HTTPException(e.status, str(e))
    svc.integrations.record_event("telegram", ref, "proposal", user["id"], UUID(out["proposal_id"]))
    return {**out, "next": "The sender must tap Confirm in the Quixotic Approvals bot; then reviewers decide. Nothing is live yet."}


class StatusIn(Who):
    proposal_id: UUID


@router.post("/hermes/proposal-status")
def hermes_status(body: StatusIn, _: bytes = Depends(signed), svc: Services = Depends(get_services)):
    user, p = _person(svc, body.telegram_user_id)
    x = svc.knowledge.get_proposal(body.proposal_id)
    if x is None or (x["submitted_by"] != user["id"] and not may_review(p, KnowledgeService(svc).proposal_departments(x))):
        raise HTTPException(404, "proposal not found")
    approvals = sum(1 for d in svc.knowledge.decisions(body.proposal_id) if d["decision"] == "approve")
    return {"title": x["title"], "status": x["status"], "approvals": approvals, "required_approvals": x["required_approvals"],
            "error": x["error"], "link": f"{svc.settings.public_url}/#/approvals"}


class GapIn(Who):
    question: str = Field(min_length=3, max_length=1000)


@router.post("/hermes/knowledge-gaps")
def hermes_gap(body: GapIn, _: bytes = Depends(signed), svc: Services = Depends(get_services)):
    """§9 step 3 "report knowledge gap"."""
    from .gaps import record_gap
    user, p = _person(svc, body.telegram_user_id)
    gid = record_gap(svc, p, body.question, None)
    return {"gap_id": str(gid) if gid else None}


# ---- Telegram webhook for the approvals bot ----
@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
                           svc: Services = Depends(get_services)):
    bot = getattr(svc, "approvals_bot", None)
    secret = svc.settings.telegram_webhook_secret
    if bot is None or not secret:
        raise HTTPException(404, "not found")
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(x_telegram_bot_api_secret_token, secret):
        raise HTTPException(401, "bad secret")
    bot.handle_update(await request.json())
    return {"ok": True}


# ---- Obsidian vault push (called by the Git server hook) ----
class VaultPush(BaseModel):
    branch: str = Field(min_length=1, max_length=120)
    commit: str = Field(min_length=7, max_length=64)


@router.post("/vault/push", status_code=202)
def vault_push(body: VaultPush, _: bytes = Depends(signed), svc: Services = Depends(get_services)):
    from ...knowledge.vault_sync import VaultSync
    if not svc.settings.vault_contributors_dir:
        raise HTTPException(404, "not found")
    return VaultSync(svc).sync_branch(body.branch, body.commit)


# ---- admin: link accounts (§9 step 1 allowlist + identity mapping) ----
class IdentityIn(BaseModel):
    platform: Literal["telegram", "obsidian"]
    external_id: str = Field(min_length=1, max_length=120)
    user_id: UUID
    label: Optional[str] = Field(default=None, max_length=80)


@admin.get("/identities")
def list_identities(_=Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    return {"identities": [{**r, "id": str(r["id"]), "user_id": str(r["user_id"])} for r in svc.integrations.identities()],
            "telegram": bool(svc.settings.telegram_bot_token), "hermes": bool(svc.settings.hermes_shared_secret),
            "obsidian": bool(svc.settings.vault_contributors_dir)}


@admin.post("/identities", status_code=201)
def add_identity(body: IdentityIn, p=Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    ext = body.external_id.strip()
    if body.platform == "telegram" and not ext.lstrip("-").isdigit():
        raise HTTPException(422, "a Telegram ID is a number (the user sends /start to the Quixotic Approvals bot to see it)")
    if body.platform == "obsidian" and not ext.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(422, "use a simple branch name, e.g. ceo")
    user = svc.users.get(body.user_id)
    if not user or user["account_status"] != "active":
        raise HTTPException(422, "link only active accounts")
    try:
        iid = svc.integrations.add_identity(body.platform, ext, body.user_id, body.label, p.user_id)
    except Exception:
        raise HTTPException(409, "this account is already linked")
    audit.record(svc.ops, audit.PERMISSION_CHANGE, p.user_id, p.employee_id, action="integration_identity_linked", platform=body.platform,
                 user=body.user_id)
    if body.platform == "obsidian":
        from ...knowledge.vault_sync import queue_view_refresh
        queue_view_refresh(svc, p.user_id, ext)                    # creates their private repository with their view
    return {"id": str(iid)}


@admin.get("/obsidian/activity")
def obsidian_activity(p=Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    """Owner request 2026-10-20: per-contributor activity — pushes, the proposals they became (and their review state),
    view refreshes and Git conflicts. Contributor = `proposals/<name>`."""
    out = []
    for r in svc.integrations.activity("obsidian"):
        eid = r["event_id"]
        name = (eid.split(":", 2)[1] if r["kind"] in ("view_refresh", "conflict") else eid.split(":", 1)[0].removeprefix("proposals/"))
        out.append({"contributor": name, "kind": r["kind"], "at": r["received_at"].isoformat(), "person": r["full_name"],
                    "note": eid.split(":", 2)[2] if r["kind"] == "proposal" else None, "proposal_id": str(r["proposal_id"]) if r["proposal_id"] else None,
                    "proposal_title": r["proposal_title"], "proposal_status": r["proposal_status"]})
    return {"enabled": bool(svc.settings.vault_contributors_dir), "events": out}


@admin.delete("/identities/{identity_id}", status_code=204)
def remove_identity(identity_id: UUID, p=Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    ident = next((i for i in svc.integrations.identities() if i["id"] == identity_id), None)
    if not svc.integrations.remove_identity(identity_id):
        raise HTTPException(404, "not found")
    if ident and ident["platform"] == "obsidian":
        from ...knowledge.vault_sync import queue_view_refresh
        queue_view_refresh(svc, p.user_id, ident["external_id"], empty=True)     # unlinked: their repository keeps no notes
    audit.record(svc.ops, audit.PERMISSION_CHANGE, p.user_id, p.employee_id, action="integration_identity_removed", identity=identity_id)
