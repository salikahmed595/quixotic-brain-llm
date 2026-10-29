"""Client Brain S2: clients and their typed, sourced memories (owner spec 2026-10-29 §3, §4; not in the PRD, docs/PRD_GAPS.md).

Anyone who can ask questions may use the clients of their own departments (owner default: department-wide); administrators
and other all-department roles see every department. Scope is enforced server-side on every call; another department's
client answers 404 so its existence does not leak. Every change is an append-only event with the actor
(client_memory_events), which is the audit trail for this data."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ...client_memory.rules import CATEGORIES, STATUSES, MemoryError_
from ...permissions.access import PermissionDenied, Principal
from ...permissions.roles import P
from ..deps import get_services, require
from ..services import Services

router = APIRouter(prefix="/v1/clients", tags=["clients"])


class ClientIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    discord_handle: Optional[str] = Field(default=None, max_length=120)
    department: Optional[str] = None              # name; default = the caller's only department


class MemoryIn(BaseModel):
    category: Literal[CATEGORIES]                 # type: ignore[valid-type]
    statement: str = Field(min_length=1, max_length=500)
    value: str = Field(default="", max_length=200)
    status: Literal[STATUSES] = "confirmed"       # type: ignore[valid-type]
    source_type: Literal["discord_message", "order", "payment", "employee_note"]
    source_id: str = Field(default="", max_length=200)
    source_text: str = Field(default="", max_length=2000)
    order_ref: Optional[str] = Field(default=None, max_length=80)
    valid_until: Optional[datetime] = None
    supersedes_memory_id: Optional[UUID] = None


def _scope(p: Principal) -> Optional[set]:
    return None if p.all_departments else set(p.department_ids)


def _store(svc: Services):
    if getattr(svc, "clients", None) is None:
        raise HTTPException(503, "client memory is not available on this server")
    return svc.clients


def _names(svc) -> dict:
    return {d["id"]: d["name"] for d in svc.users.list_departments()}


def _client_out(c: dict, names: dict) -> dict:
    return {"id": str(c["id"]), "display_name": c["display_name"], "discord_handle": c["discord_handle"],
            "department": names.get(c["department_id"]), "created_at": c["created_at"].isoformat()}


def _memory_out(m: dict) -> dict:
    keys = ("category", "statement", "value", "status", "source_type", "source_id", "source_text", "order_ref")
    out = {k: m.get(k) for k in keys} | {"id": str(m["id"])}
    for k in ("observed_at", "valid_until", "deleted_at"):
        out[k] = m[k].isoformat() if m.get(k) else None
    for k in ("superseded_by", "supersedes_memory_id", "created_by", "reviewed_by"):
        out[k] = str(m[k]) if m.get(k) else None
    return out


@router.post("", status_code=201)
def create_client(body: ClientIn, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    store, names = _store(svc), _names(svc)
    if body.department:
        d = svc.users.department_by_name(body.department)
        if not d:
            raise HTTPException(422, f"unknown department {body.department!r}")
        dept = d["id"]
        if not p.all_departments and dept not in p.department_ids:
            raise HTTPException(403, "you can only add clients to your own departments")
    elif len(p.department_ids) == 1:
        dept = next(iter(p.department_ids))
    else:
        raise HTTPException(422, "choose the client's department")
    try:
        cid = store.create_client(dept, body.display_name, body.discord_handle, p.user_id)
    except ValueError as e:
        raise HTTPException(409 if "already" in str(e) else 422, str(e)) from None
    return {"id": str(cid), "display_name": " ".join(body.display_name.split()), "discord_handle": body.discord_handle,
            "department": names.get(dept)}


@router.get("")
def find_clients(q: str = "", p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    names = _names(svc)
    return {"clients": [_client_out(c, names) for c in _store(svc).find_clients(q[:120], _scope(p))]}


@router.get("/{client_id}")
def get_client(client_id: UUID, order_ref: Optional[str] = None, p: Principal = Depends(require(P.ASK)),
               svc: Services = Depends(get_services)):
    store = _store(svc)
    try:
        client = store.get_client(client_id, _scope(p))
        facts = store.current(client_id, _scope(p), order_ref)
    except PermissionDenied:
        raise HTTPException(404, "client not found") from None
    return {"client": _client_out(client, _names(svc)), "facts": [_memory_out(m) for m in facts]}


@router.get("/{client_id}/history")
def client_history(client_id: UUID, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    store = _store(svc)
    try:
        memories, events = store.history(client_id, _scope(p)), store.events(client_id, _scope(p))
    except PermissionDenied:
        raise HTTPException(404, "client not found") from None
    return {"memories": [_memory_out(m) for m in memories],
            "events": [{"event": e["event"], "memory_id": str(e["memory_id"]) if e["memory_id"] else None,
                        "actor": str(e["actor"]) if e["actor"] else None, "at": e["at"].isoformat()} for e in events]}


@router.post("/{client_id}/memories", status_code=201)
def add_memory(client_id: UUID, body: MemoryIn, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    try:
        mid = _store(svc).add_memory(client_id, body.model_dump(), p.user_id, _scope(p))
    except PermissionDenied:
        raise HTTPException(404, "client not found") from None
    except MemoryError_ as e:
        raise HTTPException(422, str(e)) from None
    return {"id": str(mid)}


@router.post("/memories/{memory_id}/confirm", status_code=204)
def confirm_memory(memory_id: UUID, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    try:
        _store(svc).confirm_memory(memory_id, p.user_id, _scope(p))
    except PermissionDenied:
        raise HTTPException(404, "memory not found") from None
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    return Response(status_code=204)


@router.delete("/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: UUID, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    try:
        _store(svc).delete_memory(memory_id, p.user_id, _scope(p))
    except PermissionDenied:
        raise HTTPException(404, "memory not found") from None
    return Response(status_code=204)
