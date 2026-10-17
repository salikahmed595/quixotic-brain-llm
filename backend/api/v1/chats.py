"""Chats — PRD §6 FR-CHAT-01 (new chat, persistence, rename/delete, search own titles and messages), FR-CHAT-09 (only your own
chats), §11 chat contract (`POST /chats`, `GET /chats`, `GET /chats/{id}`, `POST /chats/{id}/messages`, `DELETE /chats/{id}`).

`/v1/conversations` (the earlier path) stays available with the same behaviour."""
from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...permissions.access import Principal
from ...permissions.roles import P
from ..deps import Caller, get_services, require
from ..services import Services
from . import ask as ask_api

router = APIRouter(prefix="/v1/chats", tags=["chats"])
NEW_CHAT = "New chat"


def _store(svc: Services):
    if getattr(svc, "conversations", None) is None:
        raise HTTPException(503, "chat history is not available")
    return svc.conversations


@router.get("")
def list_chats(q: Optional[str] = None, limit: int = 200, me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    q = (q or "").strip()
    if q:
        return {"chats": _store(svc).search(me.user_id, q[:100], min(limit, 200))}
    return {"chats": _store(svc).list(me.user_id, min(limit, 500))}


class NewChat(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)


@router.post("", status_code=201)
def create_chat(body: NewChat = NewChat(), me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    title = " ".join((body.title or "").split()) or NEW_CHAT
    cid = _store(svc).create(me.user_id, title, None, None)
    return {"id": str(cid), "title": title}


@router.get("/{chat_id}")
def get_chat(chat_id: UUID, me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    conv = _store(svc).get(me.user_id, chat_id)
    if conv is None:
        raise HTTPException(404, "chat not found")
    return conv


class Message(BaseModel):
    content: str = Field(min_length=1, max_length=ask_api.MAX_QUESTION_CHARS)
    mode: Literal["answer", "search"] = "answer"          # "search" = documents only, no generated answer
    department: Optional[str] = None                      # §6 FR-CHAT-06 scope from the Company Knowledge dropdown


@router.post("/{chat_id}/messages")
def post_message(chat_id: UUID, body: Message, me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    """Ask inside a chat (§11). The question and the reply are saved to this chat."""
    store = _store(svc)
    conv = store.get(me.user_id, chat_id)
    if conv is None:
        raise HTTPException(404, "chat not found")
    caller = Caller(principal=me)
    if body.mode == "search":
        out = ask_api.search(ask_api.SearchRequest(question=body.content, department=body.department, conversation_id=chat_id), caller, svc)
    else:
        out = ask_api.ask(ask_api.AskRequest(question=body.content, department=body.department, conversation_id=chat_id), caller, svc)
    if conv["title"] == NEW_CHAT and not conv["messages"]:          # the first question names the chat
        title = " ".join(body.content.split())
        store.rename(me.user_id, chat_id, (title[:60] + "…") if len(title) > 60 else title)
    return out


class Rename(BaseModel):
    title: str = Field(max_length=200)


@router.patch("/{chat_id}")
def rename_chat(chat_id: UUID, body: Rename, me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    title = " ".join(body.title.split())[:120]
    if not title:
        raise HTTPException(422, "title cannot be empty")
    if not _store(svc).rename(me.user_id, chat_id, title):
        raise HTTPException(404, "chat not found")
    return {"id": str(chat_id), "title": title}


@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: UUID, me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    if not _store(svc).delete(me.user_id, chat_id):
        raise HTTPException(404, "chat not found")


@router.delete("", status_code=200)
def delete_all_chats(me: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    return {"deleted": _store(svc).delete_all(me.user_id)}
