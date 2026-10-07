"""Chat history — owner request (ChatGPT-style new chat / previous chats). A user only ever sees their own chats."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...permissions.access import Principal
from ...permissions.roles import P
from ..deps import get_services, require
from ..services import Services

router = APIRouter(prefix="/v1/conversations", tags=["chats"])


class Rename(BaseModel):
    title: str


def _store(svc: Services):
    if getattr(svc, "conversations", None) is None:
        raise HTTPException(503, "chat history is not available")
    return svc.conversations


@router.get("")
def list_chats(limit: int = 200, me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    return {"conversations": _store(svc).list(me.user_id, min(limit, 500))}


@router.delete("", status_code=200)
def delete_all_chats(me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    return {"deleted": _store(svc).delete_all(me.user_id)}


@router.get("/{conversation_id}")
def get_chat(conversation_id: UUID, me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    conv = _store(svc).get(me.user_id, conversation_id)
    if conv is None:
        raise HTTPException(404, "chat not found")
    return conv


@router.patch("/{conversation_id}")
def rename_chat(conversation_id: UUID, body: Rename, me: Principal = Depends(require(P.ASK)),
                svc: Services = Depends(get_services)):
    title = " ".join(body.title.split())[:120]
    if not title:
        raise HTTPException(422, "title cannot be empty")
    if not _store(svc).rename(me.user_id, conversation_id, title):
        raise HTTPException(404, "chat not found")
    return {"id": str(conversation_id), "title": title}


@router.delete("/{conversation_id}", status_code=204)
def delete_chat(conversation_id: UUID, me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    if not _store(svc).delete(me.user_id, conversation_id):
        raise HTTPException(404, "chat not found")
