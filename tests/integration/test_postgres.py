"""End-to-end against real PostgreSQL + pgvector: schema, workflow, ingestion, permissions-before-retrieval, hybrid search, ask."""
import json
import os
from uuid import uuid4

import psycopg
import pytest

from backend.auth.security import generate_api_key, hash_password
from backend.ingestion.pipeline import IngestionService
from backend.permissions.access import Principal, resolve_department_scope
from backend.permissions.roles import Role
from backend.retrieval.ask import AskService
from backend.retrieval.language import LanguageService
from backend.retrieval.search import SearchService
from tests.conftest import make_settings
from tests.fakes import FakeGenerator
from tests.integration.conftest import HashEmbedder, MemStorage

pytestmark = pytest.mark.skipif(not os.environ.get("QB_TEST_DATABASE_URL"),
                                reason="needs a real PostgreSQL (QB_TEST_DATABASE_URL)")

POLICY = "# Discount Approval\nCustomers buying 3 or more artworks can receive up to 10% discount after manager approval."
HR = "# Annual Leave\nFull time employees receive annual leave per the HR leave policy."


def setup(stores, settings):
    u, k = stores["users"], stores["knowledge"]
    sales, hr = u.department_by_name("Sales")["id"], u.department_by_name("HR")["id"]
    admin = u.create_user(f"emp_{uuid4().hex[:6]}", f"{uuid4().hex[:6]}@q.ai", "Admin", hash_password("x"),
                          Role.SYSTEM_ADMIN, [])
    emb, lang, storage = HashEmbedder(), LanguageService(settings.roman_urdu_min_ratio), MemStorage()
    return sales, hr, admin, emb, lang, IngestionService(k, storage, emb, lang, settings)


def publish(stores, ing, admin, depts, title, body, doc_type="policy"):
    k = stores["knowledge"]
    item, vid = k.create_item_with_first_version(title, "Pricing", doc_type, depts, body, None, "Sales + Managers", None, admin)
    ing.process_version(vid)
    for s in ("submitted", "pending_review", "approved", "active"):
        k.transition(vid, s, admin)
    return item, vid


def test_full_brain_flow(stores):
    s = make_settings(candidate_count=20, final_chunk_count=5, chunk_size=200, chunk_overlap=20,
                      confidence_high=0.3, confidence_medium=0.1, confidence_vector_high=0.3, confidence_vector_medium=0.1)      # thresholds suited to the hashing test embedder
    sales, hr, admin, emb, lang, ing = setup(stores, s)
    item, v1 = publish(stores, ing, admin, [sales], "Sales Pricing Policy", POLICY)
    publish(stores, ing, admin, [hr], "HR Leave Policy", HR)

    with stores["pool"].connection() as c:                         # chunk metadata follows PRD §14
        meta = c.execute("SELECT metadata, embedding_model FROM chunks WHERE version_id=%s", (v1,)).fetchone()
    assert set(meta["metadata"]) == {"company", "department", "document_type", "category", "access_level", "status",
                                     "version", "language", "created_at", "updated_at"}
    assert meta["metadata"]["company"] == "quixotic" and meta["metadata"]["department"] == ["Sales"]
    assert meta["embedding_model"] == emb.name

    search = SearchService(stores["retrieval"], emb, None, lang, s)
    ask = AskService(search, FakeGenerator(), s)

    # permissions BEFORE retrieval: a Sales-only user never sees HR knowledge
    sales_user = Principal(uuid4(), "e1", Role.EMPLOYEE, frozenset({sales}))
    all_ids = stores["users"].all_department_ids()
    scope = resolve_department_scope(sales_user, all_ids)
    assert all(c.title != "HR Leave Policy" for c in search.search("annual leave for employees", scope).candidates)
    admin_scope = resolve_department_scope(Principal(admin, "a", Role.SYSTEM_ADMIN, frozenset()), all_ids)
    assert any(c.title == "HR Leave Policy" for c in search.search("annual leave for employees", admin_scope).candidates)

    # hybrid retrieval finds the policy and returns section/version for sources (§30)
    top = search.search("can we give 20% discount for artworks", scope).candidates[0]
    assert top.title == "Sales Pricing Policy" and top.section == "Discount Approval" and top.version == 1
    assert top.vector_score is not None

    # §15: a new version replaces the old one once active; the old one is archived and no longer retrieved
    v2 = stores["knowledge"].create_new_version(item, "# Discount Approval\nMaximum discount is 5% after manager approval.",
                                                None, None, None, admin)
    ing.process_version(v2)
    for st in ("submitted", "pending_review", "approved", "active"):
        stores["knowledge"].transition(v2, st, admin)
    assert stores["knowledge"].get_version(v1)["status"] == "archived"
    assert stores["knowledge"].get_version(v2)["status"] == "active"
    assert {c.version for c in search.search("maximum discount artworks", scope).candidates} == {2}
    assert {c.version for c in search.search("maximum discount artworks", scope, include_archived=True).candidates} == {1, 2}

    # draft knowledge is invisible to retrieval (status = active default)
    _, draft = stores["knowledge"].create_item_with_first_version("Secret Draft", None, "policy", [sales],
                                                                  "zebra unicorn", None, None, None, admin)
    ing.process_version(draft)
    found = search.search("zebra unicorn", scope)
    assert all(c.title != "Secret Draft" for c in found.candidates) and found.confidence == "low"   # nearest neighbours are unrelated -> low

    res = ask.ask("can we give 20% discount?", scope)               # grounded answer with sources
    assert res.found is True and res.sources[0]["title"] == "Sales Pricing Policy"


def test_one_active_version_constraint_and_history(stores):
    s = make_settings(chunk_size=200, chunk_overlap=20)
    sales, _, admin, emb, lang, ing = setup(stores, s)
    k = stores["knowledge"]
    item, v1 = publish(stores, ing, admin, [sales], "Constraint Policy", POLICY)
    v2 = k.create_new_version(item, "new", None, None, None, admin)
    with pytest.raises(psycopg.errors.UniqueViolation), stores["pool"].connection() as c:
        c.execute("UPDATE knowledge_versions SET status='active' WHERE id=%s", (v2,))   # bypassing transition(): the DB still protects §15
    assert [h["to_status"] for h in k.history(v1)] == ["draft", "submitted", "pending_review", "approved", "active"]


def test_ops_stores_keys_jobs_logs_feedback_dashboard(stores):
    ops = stores["ops"]
    s = make_settings(chunk_size=200, chunk_overlap=20)
    sales, _, admin, emb, lang, ing = setup(stores, s)
    publish(stores, ing, admin, [sales], "Dash Policy", POLICY)

    from datetime import datetime, timedelta, timezone
    full, prefix, digest, last4 = generate_api_key()
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    kid = ops.create_api_key("Call center", prefix, digest, last4, ["ask", "search"], [], None, expires, admin)   # all departments, no rate limit
    row = ops.api_key_by_hash(digest)
    assert row["id"] == kid and row["rate_limit_per_minute"] is None and row["allowed_department_ids"] == [] and row["created_by"] == admin
    assert abs((row["expires_at"] - expires).total_seconds()) < 1 and row["last4"] == full[-4:]
    listed = ops.list_api_keys()[0]
    assert "key_hash" not in listed and listed["key_prefix"] == "qx_live_" and listed["last4"] == last4
    forever = ops.create_api_key("Never expires", prefix, hash_password("x"), "abcd", ["ask"], [sales], 30, None, admin)
    assert [k for k in ops.list_api_keys() if k["id"] == forever][0]["expires_at"] is None
    assert ops.revoke_api_key(kid) and ops.api_key_by_hash(digest)["status"] == "revoked"

    job = ops.create_job("discord.import", {"x": 1}, admin, total=7043)
    ops.update_job(job, status="running", done=5143)
    j = ops.get_job(job)
    assert (j["status"], j["progress_done"], j["progress_total"]) == ("running", 5143, 7043)      # §47 progress

    qid = ops.log_query(user_id=admin, api_key_id=None, department_id=sales, mode="general",
                        original="customer paisay wapis mang rha hy", normalized="customer paise wapas mang raha hai",
                        language="roman_urdu", confidence="low", score=0.1, found=False,
                        retrieved=[{"title": "Dash Policy"}], answer=None, latency_ms=12)
    assert ops.add_feedback(qid, admin, True, "sale_closed", "offered 10%", None)
    assert ops.failed_questions()[0]["original_query"] == "customer paisay wapis mang rha hy"
    ops.audit("user_login", admin, "emp", {"ok": True})
    assert ops.list_audit(10, "user_login")[0]["detail"] == {"ok": True}

    ops.insert_sales_memory({"conversation_id": "4821", "channel": "discord", "scenario": "price objection",
                             "customer_message": "too expensive", "agent_response": "I understand", "outcome": "closed",
                             "sale_value": 180, "discount_given": 10, "currency": "USD", "language": "english",
                             "quality_score": 0.91}, emb.embed("too expensive"), emb.name, sales)
    cases = stores["retrieval"].sales_search(emb.embed("this is too expensive"), emb.name, frozenset({sales}), 5)
    assert [c.outcome for c in cases] == ["closed"]
    assert stores["retrieval"].sales_search(emb.embed("x"), emb.name, frozenset(), 5) == []

    d = stores["analytics"].dashboard(None)
    assert d["knowledge_chunks"] >= 1 and d["sales_memories"] >= 1 and d["departments"] == 10 and d["questions_this_week"] >= 1
    assert d["retrieval_success"] == 0.0 and d["most_used_sources"][0]["title"] == "Dash Policy"
    assert stores["analytics"].knowledge_health()["active_documents"] >= 1
    assert stores["analytics"].dashboard(frozenset())["knowledge_chunks"] == 0


def test_user_login_lookup_and_principal(stores):
    u = stores["users"]
    sales = u.department_by_name("Sales")["id"]
    uid = u.create_user("emp_104_t", "Ali.T@Quixotic.AI", "Ali", hash_password("pw"), Role.DEPARTMENT_REVIEWER, [sales])
    assert u.get_by_login("emp_104_t")["id"] == uid and u.get_by_login("ali.t@quixotic.ai")["id"] == uid   # §41
    u.update_department(sales, reviewer_ids=[uid])
    p = u.principal(u.get(uid))
    assert p.role is Role.DEPARTMENT_REVIEWER and p.department_ids == {sales} and p.managed_department_ids == {sales}
    assert u.set_status(uid, "suspended", None, "test") == "active"                      # PRD §5 FR-AUTH-05
    row = u.get_by_login("emp_104_t")
    assert row["account_status"] == "suspended" and row["is_active"] is False and row["approval_status"] == "approved"
    assert [h["to_status"] for h in u.status_history(uid)] == ["active", "suspended"]  # FR-AUTH-07


def test_chat_history_store_on_real_postgres(stores, db):
    from backend.database.conversations import ConversationStore
    chats = ConversationStore(db, "quixotic")
    users = stores["users"]
    a = users.create_user("chat_a", "a@q.ai", "A", hash_password("x"), Role.EMPLOYEE, [])
    b = users.create_user("chat_b", "b@q.ai", "B", hash_password("x"), Role.EMPLOYEE, [])
    cid = chats.create(a, "Refund question", "general", None)
    chats.add_exchange(cid, {"text": "What is our refund policy?"},
                       {"kind": "ask", "answer": "Refunds are reviewed first.", "sources": [{"title": "Refund Policy", "version": 1}]})
    chats.add_exchange(cid, {"text": "and enterprise?"}, {"kind": "ask", "answer": "Same process."})
    conv = chats.get(a, cid)
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant", "user", "assistant"]
    assert conv["messages"][1]["content"]["sources"][0]["title"] == "Refund Policy"          # JSON round-trips intact
    other = chats.create(a, "Newer chat", None, None)
    assert [c["title"] for c in chats.list(a)] == ["Newer chat", "Refund question"]            # most recent first
    chats.add_exchange(cid, {"text": "x"}, {"kind": "ask", "answer": "y"})
    assert [c["title"] for c in chats.list(a)][0] == "Refund question"                         # a new message moves a chat to the top
    # privacy: user B can neither see nor change user A's chats
    assert chats.list(b) == [] and chats.get(b, cid) is None and not chats.owns(b, cid)
    assert not chats.rename(b, cid, "hijack") and not chats.delete(b, cid)
    assert chats.rename(a, cid, "Renamed") and chats.get(a, cid)["title"] == "Renamed"
    assert chats.delete(a, cid) and chats.get(a, cid) is None and [c["id"] for c in chats.list(a)] == [other]
    with db.connection() as c:                                                                  # messages go with the chat
        assert c.execute("select count(*) n from conversation_messages where conversation_id=%s", (cid,)).fetchone()["n"] == 0


def test_pool_connections_use_iterative_hnsw_scan(db):
    """Without it a small department gets zero hits when a big one has near-duplicates (measured in the RAG audit)."""
    with db.connection() as c:
        assert c.execute("SHOW hnsw.iterative_scan").fetchone()["hnsw.iterative_scan"] == "relaxed_order"


def test_vocabulary_store_on_real_postgres(stores):
    ops = stores["ops"]
    a = ops.add_vocabulary("Ghar se kaam", "work from home", None)
    again = ops.add_vocabulary("ghar SE kaam", "remote work", None)             # same phrase, any case: replaces the meaning
    assert again == a and [(e["phrase"], e["meaning"]) for e in ops.list_vocabulary()] == [("Ghar se kaam", "remote work")]
    ops.add_vocabulary("چھٹی", "leave", None)
    assert {e["meaning"] for e in ops.list_vocabulary()} == {"remote work", "leave"}
    assert ops.delete_vocabulary(a) and not ops.delete_vocabulary(a) and len(ops.list_vocabulary()) == 1


def test_structured_sales_import_list_search_and_undo(stores):          # owner request (2026-10-08)
    from backend.sales_memory.importer import SalesMemoryImporter
    ops = stores["ops"]
    sales, _, admin, emb, lang, _ = setup(stores, make_settings())
    job = ops.create_job("discord.import", {"department_id": str(sales), "filename": "upsellers.json"}, admin)
    raw = json.dumps([{"conversation_id": 1, "customer_objection": "price too high", "customer_message": "too expensive for me",
                       "agent_response": "I understand", "scenario": "price objection", "stage": "objection", "outcome": "closed"}]).encode()
    assert SalesMemoryImporter(ops, emb, lang, None, None).run(raw, sales, job) == 1
    ops.update_job(job, status="succeeded")
    c = stores["retrieval"].sales_search(emb.embed("too expensive"), emb.name, frozenset({sales}), 5)[0]
    assert (c.customer_objection, c.sales_stage) == ("price too high", "objection")
    row = ops.sales_memory_imports()[0]
    assert (row["filename"], row["department"], row["stored"], row["status"]) == ("upsellers.json", "Sales", 1, "succeeded")
    assert ops.delete_sales_memory_import(job) == 1 and ops.sales_memory_imports()[0]["stored"] == 0
