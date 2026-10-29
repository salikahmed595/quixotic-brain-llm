"""Client Brain S1 against REAL PostgreSQL: clients, typed memories, supersession history, events, department scope,
alias collisions and deletion. Owner spec 2026-10-29 §3, §4, §11; docs/CLIENT_BRAIN_GAP_ANALYSIS.md."""
import pytest

from backend.client_memory.rules import MemoryError_
from backend.database.client_memory import ClientMemoryStore
from backend.permissions.access import PermissionDenied


@pytest.fixture
def cm(stores):
    sales = stores["users"].create_department("Sales CM")
    finance = stores["users"].create_department("Finance CM")
    return ClientMemoryStore(stores["pool"], "quixotic"), sales, finance


def fact(category, value, **kw):
    return {"category": category, "statement": f"{category} is {value}", "value": value, "status": "confirmed",
            "source_type": "discord_message", "source_text": f"client wrote: {value}", **kw}


def test_budget_change_keeps_history_and_current_view_uses_the_newest(cm):
    store, sales, _ = cm
    cid = store.create_client(sales, "NightOwl", "nightowl#0001", actor=None)
    old = store.add_memory(cid, fact("budget", "$300", order_ref="banner-1"), actor=None, departments={sales})
    new = store.add_memory(cid, fact("budget", "$70", order_ref="banner-1"), actor=None, departments={sales})
    assert [f["value"] for f in store.current(cid, {sales}, order_ref="banner-1")] == ["$70"]
    hist = {m["id"]: m for m in store.history(cid, {sales})}
    assert hist[old]["superseded_by"] == new and hist[old]["value"] == "$300"          # kept, not overwritten
    events = [e["event"] for e in store.events(cid, {sales})]
    assert events.count("created") == 2 and events.count("superseded") == 1


def test_other_departments_cannot_read_or_write_a_client(cm):
    store, sales, finance = cm
    cid = store.create_client(sales, "Kitsu", None, actor=None)
    store.add_memory(cid, fact("game", "Valorant"), actor=None, departments={sales})
    with pytest.raises(PermissionDenied):
        store.current(cid, {finance})
    with pytest.raises(PermissionDenied):
        store.add_memory(cid, fact("game", "Fortnite"), actor=None, departments={finance})
    assert store.find_clients("Kitsu", {finance}) == []
    assert len(store.current(cid, None)) == 1                       # None = administrators, all departments


def test_two_clients_with_the_same_alias_never_share_memories(cm):
    store, sales, _ = cm
    a = store.create_client(sales, "Shadow", "shadow#1111", actor=None)
    b = store.create_client(sales, "Shadow", "shadow#2222", actor=None)
    store.add_memory(a, fact("art_preference", "purple cyberpunk"), actor=None, departments={sales})
    store.add_memory(b, fact("art_preference", "pastel cats"), actor=None, departments={sales})
    assert [f["value"] for f in store.current(a, {sales})] == ["purple cyberpunk"]
    assert [f["value"] for f in store.current(b, {sales})] == ["pastel cats"]
    assert {c["id"] for c in store.find_clients("shadow", {sales})} == {a, b}


def test_same_discord_handle_twice_in_a_department_is_refused(cm):
    store, sales, _ = cm
    store.create_client(sales, "Shadow", "Shadow#1111", actor=None)
    with pytest.raises(ValueError, match="already"):
        store.create_client(sales, "Other", "shadow#1111", actor=None)


def test_invalid_or_guessed_facts_are_refused_before_saving(cm):
    store, sales, _ = cm
    cid = store.create_client(sales, "Rex", None, actor=None)
    with pytest.raises(MemoryError_):
        store.add_memory(cid, fact("other", "rich", statement="client is rich"), actor=None, departments={sales})
    assert store.history(cid, {sales}) == []


def test_delete_removes_the_content_and_keeps_only_an_event(cm):
    store, sales, _ = cm
    cid = store.create_client(sales, "Rex", None, actor=None)
    mid = store.add_memory(cid, fact("deadline", "Nov 5"), actor=None, departments={sales})
    store.delete_memory(mid, actor=None, departments={sales})
    assert store.current(cid, {sales}) == []
    row = next(m for m in store.history(cid, {sales}) if m["id"] == mid)
    assert row["deleted_at"] and row["statement"] == "" and row["value"] == "" and row["source_text"] == ""
    assert [e["event"] for e in store.events(cid, {sales})][-1] == "deleted"


def test_events_are_append_only(cm, stores):
    import psycopg
    store, sales, _ = cm
    cid = store.create_client(sales, "Rex", None, actor=None)
    store.add_memory(cid, fact("game", "Valorant"), actor=None, departments={sales})
    with stores["pool"].connection() as c:
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            c.execute("DELETE FROM client_memory_events WHERE client_id=%s", (cid,))


def test_confirming_a_tentative_fact_records_the_reviewer(cm):
    store, sales, _ = cm
    uid = None
    cid = store.create_client(sales, "Rex", None, actor=uid)
    mid = store.add_memory(cid, fact("platform", "Twitch", status="tentative"), actor=None, departments={sales})
    store.confirm_memory(mid, actor=None, departments={sales})
    assert [(f["value"], f["status"]) for f in store.current(cid, {sales})] == [("Twitch", "confirmed")]
    assert "confirmed" in [e["event"] for e in store.events(cid, {sales})]
