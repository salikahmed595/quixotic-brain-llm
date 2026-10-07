"""Vocabulary: Urdu / Roman Urdu words and phrases the company teaches the system (owner request, PRD §22-§23).
A phrase as staff write it maps to its English meaning; the meaning is added to the search text of every question."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...analytics import audit
from ...permissions.access import Principal
from ...permissions.roles import P
from ..deps import get_services, require
from ..services import Services

router = APIRouter(prefix="/v1/vocabulary", tags=["vocabulary"])


class Entry(BaseModel):
    phrase: str = Field(min_length=1, max_length=80)      # e.g. "ghar se kaam"  or  "چھٹی"
    meaning: str = Field(min_length=1, max_length=120)    # e.g. "work from home" (English, as written in your documents)


@router.get("")
def list_entries(_: Principal = Depends(require(P.MANAGE_VOCABULARY)), svc: Services = Depends(get_services)):
    return {"entries": svc.ops.list_vocabulary()}


@router.post("", status_code=201)
def add_entry(body: Entry, actor: Principal = Depends(require(P.MANAGE_VOCABULARY)), svc: Services = Depends(get_services)):
    phrase, meaning = " ".join(body.phrase.split()), " ".join(body.meaning.split())
    if not phrase or not meaning:
        raise HTTPException(422, "phrase and meaning cannot be empty")
    vid = svc.ops.add_vocabulary(phrase, meaning, actor.user_id)
    svc.language.refresh_vocabulary()                       # takes effect immediately on this server
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="teach_phrase", phrase=phrase, meaning=meaning)
    return {"id": str(vid), "phrase": phrase, "meaning": meaning}


@router.delete("/{vocab_id}", status_code=204)
def delete_entry(vocab_id: UUID, actor: Principal = Depends(require(P.MANAGE_VOCABULARY)), svc: Services = Depends(get_services)):
    if not svc.ops.delete_vocabulary(vocab_id):
        raise HTTPException(404, "entry not found")
    svc.language.refresh_vocabulary()
    audit.record(svc.ops, audit.ADMIN_ACTION, actor.user_id, actor.employee_id, action="forget_phrase", entry=vocab_id)
