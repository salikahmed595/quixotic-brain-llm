"""Client Brain S1 (owner spec 2026-10-29, docs/CLIENT_BRAIN_GAP_ANALYSIS.md): rules for typed, sourced client memories.
Pure functions, no database; the SQL store is covered by tests/integration/test_client_memory_db.py."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.client_memory.rules import MemoryError_, current_facts, superseded_by, validate_memory

NOW = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)


def mem(id, category, value, order_ref=None, status="confirmed", at=NOW, **kw):
    return {"id": id, "category": category, "value": value, "statement": f"{category}: {value}", "order_ref": order_ref,
            "status": status, "observed_at": at, "valid_until": None, "deleted_at": None, "source_type": "discord_message",
            "source_text": "client said so", **kw}


# ---- validation: a fact needs a source; no guessed traits ----
def test_a_memory_needs_category_statement_and_a_source():
    good = {"category": "budget", "statement": "Budget for the banner is $70", "value": "$70", "status": "confirmed",
            "source_type": "discord_message", "source_text": "bro can u do it for $70"}
    assert validate_memory(good) == good | {"order_ref": None}
    for broken, why in ((good | {"category": "mood"}, "category"), (good | {"statement": " "}, "statement"),
                        (good | {"status": "certain"}, "status"), (good | {"source_type": ""}, "source"),
                        (good | {"source_text": "", "source_id": ""}, "source")):
        with pytest.raises(MemoryError_, match=why):
            validate_memory(broken)


@pytest.mark.parametrize("text", ["Client is rich, can pay more", "seems poor", "probably middle class", "He is an introvert",
                                  "has a high income", "can afford premium"])
def test_guessed_income_class_or_personality_is_never_stored(text):
    with pytest.raises(MemoryError_, match="not stored"):
        validate_memory({"category": "other", "statement": text, "status": "tentative", "source_type": "employee_note",
                         "source_text": "my feeling"})


# ---- supersession: newest statement wins for the relevant order, history kept ----
def test_budget_300_then_70_for_the_same_order_supersedes():
    old = mem("m1", "budget", "$300", order_ref="banner-1", at=NOW - timedelta(days=3))
    new = mem("m2", "budget", "$70", order_ref="banner-1")
    assert superseded_by(new, [old]) == ["m1"]
    facts = current_facts([old | {"superseded_by": "m2"}, new], order_ref="banner-1")
    assert [f["value"] for f in facts] == ["$70"]


def test_returning_customer_new_order_budget_does_not_touch_the_old_order():
    old_order = mem("m1", "budget", "$300", order_ref="banner-1")
    new_order = mem("m2", "budget", "$70", order_ref="emotes-2")
    assert superseded_by(new_order, [old_order]) == []
    assert [f["value"] for f in current_facts([old_order, new_order], order_ref="emotes-2")] == ["$70"]
    assert [f["value"] for f in current_facts([old_order, new_order], order_ref="banner-1")] == ["$300"]


def test_general_budget_is_used_only_when_the_order_has_none():
    general = mem("m1", "budget", "around $100")
    assert [f["value"] for f in current_facts([general], order_ref="emotes-2")] == ["around $100"]
    specific = mem("m2", "budget", "$70", order_ref="emotes-2")
    assert [f["value"] for f in current_facts([general, specific], order_ref="emotes-2")] == ["$70"]


def test_preferences_add_up_instead_of_replacing_each_other():
    a, b = mem("m1", "art_preference", "purple cyberpunk"), mem("m2", "art_preference", "anime style")
    assert superseded_by(b, [a]) == []
    assert {f["value"] for f in current_facts([a, b])} == {"purple cyberpunk", "anime style"}


def test_an_explicit_correction_supersedes_a_preference():
    a = mem("m1", "art_preference", "purple")
    b = mem("m2", "art_preference", "green, not purple", supersedes_memory_id="m1")
    assert superseded_by(b, [a]) == ["m1"]


def test_tentative_never_overrides_confirmed_and_expired_or_deleted_facts_are_not_current():
    confirmed = mem("m1", "deadline", "Nov 5")
    guess = mem("m2", "deadline", "maybe Nov 1", status="tentative")
    assert superseded_by(guess, [confirmed]) == []
    expired = mem("m3", "platform", "Twitch", valid_until=NOW - timedelta(days=1))
    deleted = mem("m4", "game", "Valorant", deleted_at=NOW)
    facts = current_facts([confirmed, guess, expired, deleted], now=NOW)
    assert [(f["value"], f["status"]) for f in facts] == [("Nov 5", "confirmed"), ("maybe Nov 1", "tentative")]
