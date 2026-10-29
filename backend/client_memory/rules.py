"""Rules for client memories, kept free of the database so they are unit-tested directly (owner spec 2026-10-29 §1, §3, §4).

- A fact needs a source (a numeric confidence is not a substitute, spec §3).
- Guessed income, class, wealth or personality is never stored (spec §1.2, §4.6).
- Budget and deadline hold one value per order (order_ref; None = the client in general): a newer confirmed or observed
  value supersedes the older one for the same order only. Other categories add up unless the new fact names the one it corrects.
- A tentative fact never supersedes; it is shown as tentative."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable, Optional

CATEGORIES = ("art_preference", "platform", "game", "communication", "budget", "deadline", "commitment", "objection", "other")
STATUSES = ("confirmed", "observed", "tentative", "unknown", "disputed")
SOURCE_TYPES = ("discord_message", "order", "payment", "employee_note")
SINGLE_VALUED = ("budget", "deadline")          # one current value per order; implementation choice, docs/PRD_GAPS.md
_GUESSED_TRAIT = re.compile(r"\b(rich|poor|wealthy|broke|middle[- ]class|upper[- ]class|lower[- ]class|income|salary|afford\w*|"
                            r"introvert\w*|extrovert\w*|personality|narcissis\w*|insecure)\b", re.I)


class MemoryError_(ValueError):
    """A memory that must not be saved (shown to the employee as the reason)."""


def validate_memory(m: dict) -> dict:
    out = dict(m)
    out.setdefault("order_ref", None)
    if out.get("category") not in CATEGORIES:
        raise MemoryError_(f"category must be one of {', '.join(CATEGORIES)}")
    if not (out.get("statement") or "").strip():
        raise MemoryError_("statement is required")
    if out.get("status") not in STATUSES:
        raise MemoryError_(f"status must be one of {', '.join(STATUSES)}")
    if out.get("source_type") not in SOURCE_TYPES or not ((out.get("source_text") or "").strip() or (out.get("source_id") or "").strip()):
        raise MemoryError_("a source is required: source_type and the exact source text or source id")
    if _GUESSED_TRAIT.search(f"{out['statement']} {out.get('value') or ''}"):
        raise MemoryError_("guessed income, class or personality is not stored")
    return out


def _live(m: dict, now: datetime) -> bool:
    vu = m.get("valid_until")
    return not m.get("deleted_at") and not m.get("superseded_by") and (vu is None or vu > now)


def superseded_by(new: dict, existing: Iterable[dict]) -> list:
    """Ids of the current memories the new one replaces."""
    if new.get("status") not in ("confirmed", "observed"):
        return []
    named = new.get("supersedes_memory_id")
    out = []
    for m in existing:
        if m.get("deleted_at") or m.get("superseded_by"):
            continue
        if named and m["id"] == named:
            out.append(m["id"])
        elif new["category"] in SINGLE_VALUED and m["category"] == new["category"] and m.get("order_ref") == new.get("order_ref"):
            out.append(m["id"])
    return out


def current_facts(memories: Iterable[dict], order_ref: Optional[str] = None, now: Optional[datetime] = None) -> list[dict]:
    """The facts to use now, oldest first. For budget / deadline: the value for `order_ref`, else the general one."""
    now = now or datetime.now(timezone.utc)
    live = sorted((m for m in memories if _live(m, now)), key=lambda m: m["observed_at"])
    out = []
    for m in live:
        if m["category"] in SINGLE_VALUED:
            if m.get("order_ref") not in (None, order_ref):
                continue
            if m.get("order_ref") is None and any(o["category"] == m["category"] and o.get("order_ref") == order_ref
                                                  and order_ref is not None and o.get("status") != "tentative" for o in live):
                continue
        out.append(m)
    return out
