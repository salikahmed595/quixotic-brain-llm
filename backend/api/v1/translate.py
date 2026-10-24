"""Translate for client — owner-approved addition 2026-10-20 (not in the PRD; docs/PRD_GAPS.md §0).

Staff (owner 2026-10-21: everyone; QB_TRANSLATE_DEPARTMENTS=all) write a client message in Urdu / Roman Urdu; the answer model returns polite, client-ready English.
It is not a knowledge answer and uses no company documents. The message is not stored (client conversations stay private,
§6 FR-CHAT-09); only an audit entry without the text is kept. Server-side permission check on every call (§3)."""
from __future__ import annotations

import re

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


# Owner 2026-10-24: "translate in any language". These are only the suggestions shown in the picker; any language name the user
# types is accepted (letters, spaces, brackets, hyphen, apostrophe; 2-40 characters) and passed to the model as the target.
TARGET_LANGUAGES = ("English", "Roman Urdu", "Urdu", "Spanish", "German", "French", "Arabic", "Portuguese", "Italian",
                    "Turkish", "Hindi", "Chinese", "Japanese", "Korean", "Russian", "Punjabi", "Persian", "Indonesian")
_LANGUAGE_NAME = re.compile(r"^[^\W\d_][\w ()'\-]{1,39}$")


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    target: str = "English"


def _same(a: str, b: str) -> bool:
    norm = lambda t: "".join(ch for ch in t.lower() if ch.isalnum())
    return norm(a) == norm(b)


@router.post("/translate")
def translate(body: TranslateIn, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    if not can_translate(p, svc):
        raise HTTPException(403, "Translate for client is not enabled for your department.")
    gen = svc.ask.generator
    if not hasattr(gen, "translate_for_client"):
        raise HTTPException(503, "The configured answer model does not support translation.")
    name = " ".join(body.target.split())
    if not _LANGUAGE_NAME.match(name) or any(ch.isdigit() for ch in name):
        raise HTTPException(422, "Type the name of a language, e.g. Spanish or Japanese.")
    target = next((t for t in TARGET_LANGUAGES if t.lower() == name.lower()), name)
    try:
        english = gen.translate_for_client(body.text.strip(), target)
        if _same(english, body.text):                 # QAI-01: came back untranslated -> one firm retry
            english = gen.translate_for_client(f"{body.text.strip()}\n\n(Translate this into {target}; do not repeat the original.)",
                                               target)
    except RuntimeError as e:                    # clear message from the model wrapper; provider details stay in the log
        raise HTTPException(503, str(e)) from None
    except Exception:
        raise HTTPException(503, "Translation is not available right now. Please try again.") from None
    if not english:
        raise HTTPException(503, "Translation came back empty. Please try again.")
    audit.record(svc.ops, audit.TRANSLATION, p.user_id, p.employee_id, chars=len(body.text))
    return {"english": english, "translation": english, "target": target}
