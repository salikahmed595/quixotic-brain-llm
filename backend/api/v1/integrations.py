"""Integrations — PRD §9 (Obsidian knowledge updates; the other chat channels were removed by the owner on 2026-10-21,
docs/PRD_GAPS.md), §15 (no autonomous changes: every Obsidian note becomes a proposal that is reviewed).

The Obsidian Git server hook signs every call with QB_VAULT_HOOK_SECRET:
    X-Quixotic-Timestamp: <unix seconds>      X-Quixotic-Signature: hex(HMAC-SHA256(secret, f"{timestamp}.{raw body}"))
Calls older than 5 minutes or with a bad signature are refused."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from ...analytics import audit
from ...permissions.roles import P
from ..deps import get_services, require
from ..services import Services

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])
admin = APIRouter(prefix="/v1/admin/integrations", tags=["integrations"])
MAX_SKEW = 300


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


async def signed(request: Request, x_quixotic_timestamp: Optional[str] = Header(default=None),
                 x_quixotic_signature: Optional[str] = Header(default=None), svc: Services = Depends(get_services)) -> bytes:
    secret = svc.settings.vault_hook_secret
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


# ---- admin: link accounts (§9 step 1 allowlist + identity mapping; Obsidian only) ----
class IdentityIn(BaseModel):
    platform: Literal["obsidian"] = "obsidian"
    external_id: str = Field(min_length=1, max_length=120)
    user_id: UUID
    label: Optional[str] = Field(default=None, max_length=80)


@admin.get("/identities")
def list_identities(_=Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    return {"identities": [{**r, "id": str(r["id"]), "user_id": str(r["user_id"])} for r in svc.integrations.identities("obsidian")],
            "obsidian": bool(svc.settings.vault_contributors_dir)}


@admin.post("/identities", status_code=201)
def add_identity(body: IdentityIn, p=Depends(require(P.MANAGE_SYSTEM)), svc: Services = Depends(get_services)):
    ext = body.external_id.strip()
    if not ext.replace("-", "").replace("_", "").isalnum():
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
