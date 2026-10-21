"""Translate for client — owner-approved addition 2026-10-20 (not in the PRD; docs/PRD_GAPS.md §0).

Staff (owner 2026-10-21: everyone; QB_TRANSLATE_DEPARTMENTS=all) write a client message in Urdu / Roman Urdu; the answer model returns polite, client-ready English.
It is not a knowledge answer and uses no company documents. The message is not stored (client conversations stay private,
§6 FR-CHAT-09); only an audit entry without the text is kept. Server-side permission check on every call (§3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...analytics import audit
from ...permissions.access import Principal
from ...permissions.roles import P
from ..deps import get_services, require
from ..services import Services

router = APIRouter(prefix="/v1", tags=["translate"])


def can_translate(p: Principal, svc: Services) -> bool:
    names = svc.settings.translate_department_names
    if not names:
        return False
    if "all" in names:                                   # owner 2026-10-21: everyone in the office may translate
        return True
    depts = {d["id"]: d["name"].lower() for d in svc.users.list_departments(include_archived=False)}
    return any(depts.get(d) in names for d in p.department_ids)


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/translate")
def translate(body: TranslateIn, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    if not can_translate(p, svc):
        raise HTTPException(403, "Translate for client is not enabled for your department.")
    gen = svc.ask.generator
    if not hasattr(gen, "translate_for_client"):
        raise HTTPException(503, "The configured answer model does not support translation.")
    try:
        english = gen.translate_for_client(body.text.strip())
    except RuntimeError as e:                    # clear message from the model wrapper; provider details stay in the log
        raise HTTPException(503, str(e)) from None
    except Exception:
        raise HTTPException(503, "Translation is not available right now. Please try again.") from None
    if not english:
        raise HTTPException(503, "Translation came back empty. Please try again.")
    audit.record(svc.ops, audit.TRANSLATION, p.user_id, p.employee_id, chars=len(body.text))
    return {"english": english}
