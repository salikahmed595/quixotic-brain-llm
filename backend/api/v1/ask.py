"""POST /v1/ask (PRD §37, §38) and POST /v1/search (PRD §39)."""
from __future__ import annotations

import time
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ...permissions.access import PermissionDenied, resolve_department_scope
from ...permissions.roles import P, can
from ..deps import Caller, api_caller, get_services, resolve_caller
from ..services import Services
from .auth import clean_preferences, learned_hints

router = APIRouter(prefix="/v1", tags=["ask"])


MAX_QUESTION_CHARS = 4000     # implementation necessity: bounds embedding/LLM cost per request (docs/PRD_GAPS.md)


class _Question(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)

    @field_validator("question")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question cannot be empty")
        return v


class AskRequest(_Question):
    user_id: Optional[str] = None            # PRD §38: employee id, used when an internal app calls with an API key
    department: Optional[str] = None         # PRD §38 (e.g. "sales")
    mode: Literal["general", "sales_coach"] = "general"      # PRD §11.4 (Search Only = /v1/search, Department Brain = `department`)
    include_archived: bool = False           # PRD §15: archived only "when explicitly requested"
    conversation_id: Optional[UUID] = None   # continue a saved chat; omit to start a new one (signed-in users only)


class SearchRequest(_Question):
    debug: bool = False                      # administrators only: also return the raw scores (used to calibrate confidence)
    user_id: Optional[str] = None
    department: Optional[str] = None
    include_archived: bool = False
    conversation_id: Optional[UUID] = None


def _remember(svc, caller, conversation_id, question, mode, department_id, assistant_content):
    """Save the exchange to the user's chat history. Not done for API-key calls (apps keep their own conversations)."""
    store = getattr(svc, "conversations", None)
    if caller.key is not None or store is None:
        return None
    uid = caller.principal.user_id
    if conversation_id is None:
        title = " ".join(question.split())
        conversation_id = store.create(uid, (title[:60] + "…") if len(title) > 60 else title, mode, department_id)
    elif not store.owns(uid, conversation_id):
        raise HTTPException(404, "chat not found")
    store.add_exchange(conversation_id, {"text": question}, assistant_content)
    return conversation_id


def _history(svc, caller, conversation_id, turns: int = 6) -> list[tuple[str, str]]:
    """The last few (question, answer) pairs of THIS user's chat, oldest first, so a short follow-up can be understood."""
    store = getattr(svc, "conversations", None)
    if conversation_id is None or caller.key is not None or store is None:
        return []
    conv = store.get(caller.principal.user_id, conversation_id)
    pairs, pending = [], None
    for m in (conv or {}).get("messages", []):
        c = m["content"]
        if m["role"] == "user":
            pending = c.get("text")
        elif pending:
            answered = c.get("kind") == "ask" and c.get("answer") and not c.get("actions")     # a real answer, not "not found"
            pairs.append([pending, c["answer"][:800] if answered else "", c.get("query_id") if answered else None])
            pending = None
    pairs = pairs[-turns:]
    ratings = {}
    if getattr(svc.settings, "feedback_learning", False) and hasattr(svc.ops, "helpful_by_query"):
        try:                                                          # a rejected answer is marked so the model does not repeat it
            ratings = svc.ops.helpful_by_query(caller.principal.user_id, [UUID(p[2]) for p in pairs if p[2]])
        except Exception:
            ratings = {}
    mark = lambda qid: None if not qid else ("helpful" if ratings.get(UUID(qid)) is True else "not helpful" if ratings.get(UUID(qid)) is False else None)
    return [(q, a, mark(qid)) for q, a, qid in pairs]


def _asker(svc, caller):
    """Who is asking and their own answer preferences, for tailoring the answer. Signed-in users only: an app calling with an
    API key is not a person with a role or preferences."""
    if caller.key is not None:
        return None, None
    p = caller.principal
    user = svc.users.get(p.user_id) or {}
    names = {d["id"]: d["name"] for d in svc.users.list_departments()}
    prefs = clean_preferences(user.get("preferences"))
    hints = learned_hints(svc, p.user_id, user) if prefs.get("learn") else []
    if hints:
        prefs["learned_style"] = hints
    return {"role": p.role.value, "departments": sorted(names[d] for d in p.department_ids if d in names)}, prefs


def _check_chat(svc, caller, conversation_id) -> None:
    """Refuse a foreign chat id before doing any work."""
    store = getattr(svc, "conversations", None)
    if conversation_id is not None and caller.key is None and store is not None and not store.owns(caller.principal.user_id, conversation_id):
        raise HTTPException(404, "chat not found")


def _scope(svc: Services, caller: Caller, department: Optional[str]):
    p = caller.principal
    requested = None
    if department:
        d = svc.users.department_by_name(department)
        if not d:
            raise HTTPException(400, f"unknown department {department!r}")
        requested = d["id"]
    try:
        scope = resolve_department_scope(p, svc.users.all_department_ids(), requested, caller.key_department_ids)
    except PermissionDenied as e:
        raise HTTPException(403, str(e))
    return scope, requested


def _log(svc, caller, requested, mode, res, answer, started):
    return svc.ops.log_query(
        user_id=caller.principal.user_id, api_key_id=caller.key["id"] if caller.key else None, department_id=requested,
        mode=mode, original=res.query.original, normalized=res.query.normalized, language=res.query.language,
        confidence=res.confidence, score=res.confidence_score, found=bool(res.retrieved) and res.confidence != "low",
        retrieved=[{"chunk_id": str(c.chunk_id), "title": c.title, "section": c.section, "version": c.version}
                   for c in res.retrieved],
        answer=answer, latency_ms=int((time.monotonic() - started) * 1000))


@router.post("/ask")
def ask(body: AskRequest, caller: Caller = Depends(api_caller("ask")), svc: Services = Depends(get_services)):
    caller = resolve_caller(caller, body.user_id, svc)
    if not can(caller.principal.role, P.ASK):
        raise HTTPException(403, "your role cannot ask questions")
    scope, requested = _scope(svc, caller, body.department)
    _check_chat(svc, caller, body.conversation_id)
    started = time.monotonic()
    asker, prefs = _asker(svc, caller)
    try:
        res = svc.ask.ask(body.question, scope, include_sales_history=body.mode == "sales_coach",
                          sales_department_ids=scope, include_archived=body.include_archived,
                          history=_history(svc, caller, body.conversation_id), asker=asker, preferences=prefs)
    except RuntimeError as e:                    # e.g. no answer-model API key configured yet
        raise HTTPException(503, str(e))
    query_id = _log(svc, caller, requested, body.mode, res, res.answer, started)
    out = {"query_id": str(query_id), "answer": res.answer, "confidence": res.confidence}   # PRD §38 shape
    if can(caller.principal.role, P.VIEW_SOURCES):
        out["sources"] = res.sources
    if res.historical_cases is not None:
        out["historical_cases"] = res.historical_cases
    if res.actions:
        out["actions"] = res.actions                                                        # PRD §32
    cid = _remember(svc, caller, body.conversation_id, body.question, body.mode, requested,
                    {"kind": "ask", "mode": body.mode, "question": body.question, **out})
    if cid is not None:
        out["conversation_id"] = str(cid)
    return out


@router.post("/search")
def search(body: SearchRequest, caller: Caller = Depends(api_caller("search")), svc: Services = Depends(get_services)):
    """Raw retrieval, no LLM generation (PRD §39)."""
    caller = resolve_caller(caller, body.user_id, svc)
    if not can(caller.principal.role, P.ASK):
        raise HTTPException(403, "your role cannot search")
    scope, requested = _scope(svc, caller, body.department)
    _check_chat(svc, caller, body.conversation_id)
    started = time.monotonic()
    history = _history(svc, caller, body.conversation_id)
    out = svc.search.search(body.question, scope, body.include_archived, previous_question=history[-1][0] if history else None)

    class _R:                                              # reuse the logging helper
        query, retrieved, confidence, confidence_score = out.query, out.candidates, out.confidence, out.confidence_score
    _log(svc, caller, requested, "search_only", _R, None, started)
    debug = body.debug and can(caller.principal.role, P.CONFIGURE_MODELS)
    result = {"results": [{"text": c.text, "score": c.best_score, "source": c.title,
                           **({"section": c.section, "vector_score": c.vector_score, "rerank_score": c.rerank_score} if debug else {})}
                          for c in out.candidates]}
    if debug:
        result["confidence"] = out.confidence
        result["timings"] = out.timings
    cid = _remember(svc, caller, body.conversation_id, body.question, "search", requested,
                    {"kind": "search", "question": body.question, **result})
    if cid is not None:
        result["conversation_id"] = str(cid)
    return result
