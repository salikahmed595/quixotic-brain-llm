import time
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.api.services import Services
from backend.auth.security import (SlidingWindowLimiter, generate_api_key, hash_api_key, hash_password, issue_token,
                                   needs_rehash, read_token, verify_password)
from backend.main import create_app
from backend.permissions.access import Principal
from backend.permissions.roles import Role
from backend.retrieval.ask import AskService
from backend.retrieval.language import LanguageService
from backend.retrieval.search import SearchService
from tests.conftest import make_settings
from tests.fakes import FakeEmbedder, FakeGenerator, FakeSessions, FakeStore, cand, session_headers


# ---- credentials ----
def test_password_hash_is_argon2id_and_legacy_scrypt_still_verifies():          # PRD §5 FR-AUTH-06
    h = hash_password("s3cret")
    assert h.startswith("$argon2id$") and not needs_rehash(h)
    assert verify_password("s3cret", h) and not verify_password("wrong", h) and h != hash_password("s3cret")
    legacy = "scrypt$16384$8$1$00112233445566778899aabbccddeeff$" + __import__("hashlib").scrypt(
        b"old", salt=bytes.fromhex("00112233445566778899aabbccddeeff"), n=16384, r=8, p=1).hex()
    assert verify_password("old", legacy) and needs_rehash(legacy)


def test_token_roundtrip_expiry_and_tamper():
    uid = uuid4()
    K, O = "k" * 40, "o" * 40
    t = issue_token(uid, K, 60, now=1000)
    assert read_token(t, K, now=1010) == uid
    assert read_token(t, K, now=1061) is None and read_token(t, O, now=1010) is None
    assert read_token(t[:-2] + "xx", K, now=1010) is None


def test_api_key_looks_like_an_llm_provider_key():       # owner decision: no app name inside the key
    full, prefix, digest, last4 = generate_api_key()
    assert full.startswith("qx_live_") and prefix == "qx_live_" and len(full) > 40 and last4 == full[-4:]
    assert digest == hash_api_key(full) and full not in digest
    assert generate_api_key()[0] != full


def test_rate_limiter_window():
    lim = SlidingWindowLimiter(60)
    assert [lim.allow("k", 2, now=t) for t in (0, 1, 2)] == [True, True, False]
    assert lim.allow("k", 2, now=61) and lim.allow("other", 2, now=2)


# ---- API with in-memory collaborators ----
SALES, HR = uuid4(), uuid4()
SECRET = "test-secret-test-secret-test-secret-123"


class Users:
    def __init__(self):
        self.rows = {
            "emp_104": dict(id=uuid4(), employee_id="emp_104", role="employee", account_status="active",
                            password_hash=hash_password("pw"), email="a@q.ai", full_name="Employee One", can_publish=False),
            "emp_9": dict(id=uuid4(), employee_id="emp_9", role="system_admin", account_status="active",
                          password_hash=hash_password("pw"), email="b@q.ai", full_name="Admin One", can_publish=True),
        }
        self.depts = {"emp_104": {SALES}, "emp_9": set()}
    def get_by_login(self, ident): return next((u for u in self.rows.values() if ident in (u["employee_id"], u["email"])), None)
    get_by_login_any = get_by_login
    def get(self, uid): return next((u for u in self.rows.values() if u["id"] == uid), None)
    def get_by_employee_id(self, e): return self.rows.get(e)
    def principal(self, u): return Principal(u["id"], u["employee_id"], Role(u["role"]), frozenset(self.depts[u["employee_id"]]),
                                             frozenset(), u.get("can_publish", False))
    def get_by_email(self, e): return next((u for u in self.rows.values() if u["email"] == e), None)
    def record_login(self, uid): pass
    def set_password_hash(self, uid, h): self.get(uid)["password_hash"] = h
    def department_by_name(self, n): return {"sales": {"id": SALES}, "hr": {"id": HR}}.get(n.lower())
    def all_department_ids(self): return frozenset({SALES, HR})
    def list_departments(self, include_archived=True): return [{"id": SALES, "name": "Sales", "status": "active"}, {"id": HR, "name": "HR", "status": "active"}]


class Ops:
    def __init__(self, key=None):
        self.audit_rows, self.logged, self.key, self.feedback = [], [], key, []
    def audit(self, event, actor, label, detail): self.audit_rows.append((event, label, detail))
    def api_key_by_hash(self, h): return self.key if self.key and self.key["key_hash"] == h else None
    def touch_api_key(self, i): pass
    def log_query(self, **kw): self.logged.append(kw); return uuid4()
    def get_query(self, qid): return next((q for q in self.logged if True), None) and {"user_id": self.logged[-1]["user_id"]}
    def add_feedback(self, *a): self.feedback.append(a); return uuid4()


def make_client(vec=None, key_perms=("ask", "search", "feedback"), rate=60, allowed=(SALES,), expires=None, status="active"):
    s = make_settings(session_secret=SECRET)
    store = FakeStore(vec=vec if vec is not None else [cand(score=.95)])
    lang = LanguageService(s.roman_urdu_min_ratio)
    search = SearchService(store, FakeEmbedder(), None, lang, s)
    full, prefix, digest, last4 = generate_api_key()
    users = Users()
    key = dict(id=uuid4(), key_hash=digest, permissions=list(key_perms), allowed_department_ids=list(allowed),
               rate_limit_per_minute=rate, expires_at=expires, status=status, created_by=users.rows["emp_9"]["id"])
    svc = Services(settings=s, users=users, knowledge=None, ops=Ops(key), analytics=None, search=search,
                   ask=AskService(search, FakeGenerator(), s), ingestion=None, importer=None, storage=None, queue=None,
                   language=lang, embedder=FakeEmbedder(), limiter=SlidingWindowLimiter(), sessions=FakeSessions())
    return TestClient(create_app(svc)), svc, store, full


def bearer(svc, ident="emp_104"):
    return session_headers(svc.sessions, svc.users.rows[ident]["id"])


def test_login_success_failure_and_audit():
    c, svc, *_ = make_client()
    assert c.post("/v1/auth/login", json={"identifier": "emp_104", "password": "nope"}).status_code == 401
    r = c.post("/v1/auth/login", json={"identifier": "a@q.ai", "password": "pw"})        # email works too
    assert r.status_code == 200 and r.json()["mfa"] == "none" and "access_token" not in r.json()
    assert "qb_session" in r.cookies and "httponly" in r.headers["set-cookie"].lower()    # §5 FR-AUTH-06
    events = [e[0] for e in svc.ops.audit_rows]
    assert events == ["failed_authentication", "user_login"]                              # §53


def test_ask_response_shape_prd_38_and_query_logged_with_original():
    c, svc, store, _ = make_client()
    r = c.post("/v1/ask", headers=bearer(svc), json={"question": "customer bol raha hai artwork expensive hai",
                                                     "department": "sales"})
    body = r.json()
    assert r.status_code == 200 and body["confidence"] == "high" and body["answer"]
    assert body["sources"][0]["title"] == "Sales Pricing Policy" and "query_id" in body
    assert svc.ops.logged[0]["original"] == "customer bol raha hai artwork expensive hai"
    assert {call[1] for call in store.calls} == {frozenset({SALES})}


def test_department_outside_authorization_is_403_and_unknown_is_400():
    c, svc, *_ = make_client()
    assert c.post("/v1/ask", headers=bearer(svc), json={"question": "q", "department": "hr"}).status_code == 403
    assert c.post("/v1/ask", headers=bearer(svc), json={"question": "q", "department": "nope"}).status_code == 400
    assert c.post("/v1/ask", json={"question": "q"}).status_code == 401


def test_low_confidence_is_logged_as_failed_question_and_returns_actions():     # PRD §32, §35
    c, svc, *_ = make_client(vec=[cand(score=0.1)])
    r = c.post("/v1/ask", headers=bearer(svc), json={"question": "new client ka onboarding SLA kya hai?"}).json()
    assert r["confidence"] == "low" and r["actions"] == ["ask_manager", "report_missing_knowledge", "search_documents"]
    assert svc.ops.logged[0]["found"] is False


def test_search_returns_raw_results_without_llm_prd_39():
    c, svc, *_ = make_client()
    r = c.post("/v1/search", headers=bearer(svc), json={"question": "refund"}).json()
    assert set(r["results"][0]) == {"text", "score", "source"} and r["results"][0]["source"] == "Sales Pricing Policy"
    assert svc.ask.generator.calls == []


def test_internal_app_with_api_key_is_limited_to_key_departments():
    c, svc, store, key = make_client()
    h = {"X-API-Key": key}
    assert c.post("/v1/ask", headers=h, json={"question": "q", "user_id": "ghost"}).status_code == 403
    ok = c.post("/v1/ask", headers=h, json={"question": "q", "user_id": "emp_9"})            # admin user, key allows only SALES
    assert ok.status_code == 200 and {call[1] for call in store.calls} == {frozenset({SALES})}
    assert c.post("/v1/ask", headers=h, json={"question": "q", "user_id": "emp_9", "department": "hr"}).status_code == 403
    assert c.post("/v1/ask", headers={"X-API-Key": "qx_live_bad_x"}, json={"question": "q"}).status_code == 401


def test_api_key_permission_and_rate_limit():
    c, svc, _, key = make_client(key_perms=("search",), rate=2)
    h = {"X-API-Key": key}
    assert c.post("/v1/ask", headers=h, json={"question": "q", "user_id": "emp_104"}).status_code == 403
    codes = [c.post("/v1/search", headers=h, json={"question": "q", "user_id": "emp_104"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_feedback_validates_outcome_values_prd_21():
    c, svc, *_ = make_client()
    qid = c.post("/v1/ask", headers=bearer(svc), json={"question": "q"}).json()["query_id"]
    ok = c.post("/v1/feedback", headers=bearer(svc), json={"query_id": qid, "helpful": True, "outcome": "sale_closed"})
    assert ok.status_code == 201 and ok.json()["validated"] is False
    bad = c.post("/v1/feedback", headers=bearer(svc), json={"query_id": qid, "outcome": "maybe"})
    assert bad.status_code == 422
    assert c.post("/v1/feedback", headers=bearer(svc), json={"query_id": qid}).status_code == 422


def test_employee_cannot_use_admin_routes():
    c, svc, *_ = make_client()
    for method, url in [("get", "/v1/admin/users"), ("get", "/v1/admin/api-keys"), ("get", "/v1/audit-logs"), ("get", "/v1/failed-questions"),
                        ("post", "/v1/admin/reindex")]:
        assert getattr(c, method)(url, headers=bearer(svc)).status_code == 403, url


def test_me_returns_what_the_ui_needs():
    c, svc, *_ = make_client()
    r = c.get("/v1/auth/me", headers=bearer(svc)).json()
    assert r["full_name"] == "Employee One" and r["role"] == "employee" and r["email"] == "a@q.ai"
    assert r["departments"] == [{"id": str(SALES), "name": "Sales"}]
    assert c.get("/v1/auth/me").status_code == 401


def test_frontend_is_served_when_configured(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<title>Quixotic AI</title>")
    monkeypatch.setenv("QB_FRONTEND_DIR", str(tmp_path))
    monkeypatch.setenv("QB_CORS_ORIGINS", "https://app.example.com")
    c, *_ = make_client()
    assert "Quixotic AI" in c.get("/").text and c.get("/v1/auth/me").status_code == 401   # API routes still win over the static mount
    pre = c.options("/v1/ask", headers={"Origin": "https://app.example.com", "Access-Control-Request-Method": "POST"})
    assert pre.headers.get("access-control-allow-origin") == "https://app.example.com"


def test_unconfigured_answer_model_is_a_clear_503_not_a_crash():
    from backend.generation.base import LazyGenerator
    c, svc, *_ = make_client()
    def boom(): raise ValueError("GEMINI_API_KEY is not set")
    svc.ask.generator = LazyGenerator(boom)
    r = c.post("/v1/ask", headers=bearer(svc), json={"question": "q"})
    assert r.status_code == 503 and "not configured" in r.json()["detail"]


def test_answer_model_failure_is_a_503_without_provider_details():               # PRD §6 FR-CHAT-07
    from backend.generation.base import LazyGenerator
    c, svc, *_ = make_client()
    class Rejected:
        def generate_answer(self, context, question): raise PermissionError("Incorrect API key provided: sk-proj-***STQA")
    svc.ask.generator = LazyGenerator(lambda: Rejected())
    r = c.post("/v1/ask", headers=bearer(svc), json={"question": "q"})
    assert r.status_code == 503 and "unavailable" in r.json()["detail"] and "sk-" not in r.json()["detail"]
