"""Portal SSO (docs/PRD_GAPS.md "Portal SSO"): signed hand-off, office binding, status push. No real people: made-up names only."""
import base64
import hashlib
import time
from uuid import uuid4

import jwt
import pyotp
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from backend.api.services import Services
from backend.api.v1.integrations import sign
from backend.auth.security import SlidingWindowLimiter, hash_password
from backend.main import create_app
from backend.retrieval.ask import AskService
from backend.retrieval.language import LanguageService
from backend.retrieval.search import SearchService
from tests.conftest import make_settings
from tests.fakes import FakeEmbedder, FakeGenerator, FakeSessions, FakeStore, cand
from tests.test_keys_and_chats import Chats
from tests.test_security_and_api import Ops, SALES, SECRET, Users

ISS, HOOK = "https://portal.test", "h" * 40
KEY = Ed25519PrivateKey.generate()
OTHER_KEY = Ed25519PrivateKey.generate()
PUB = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
UA = "testclient"                      # what Starlette's TestClient sends
UA_HASH = hashlib.sha256(UA.encode()).hexdigest()


class PortalUsers(Users):
    """The in-memory user store plus the Portal methods (the real ones are SQL in backend/database/users.py)."""
    def __init__(self):
        super().__init__()
        self.jtis, self.history = set(), {}

    def _row(self, pid): return next((u for u in self.rows.values() if u.get("portal_user_id") == pid), None)
    def get_by_portal_id(self, pid): return self._row(pid)
    def get_by_email(self, e): return next((u for u in self.rows.values() if u["email"].lower() == e.lower()), None)
    def username_or_email_taken(self, name, email):
        return any(u["employee_id"].lower() in (name.lower(), email.lower()) or u["email"].lower() in (name.lower(), email.lower())
                   for u in self.rows.values())

    def link_portal(self, uid, pid):
        u = self.get(uid)
        if u.get("portal_user_id"): return False
        u["portal_user_id"] = pid; return True

    def create_portal_user(self, pid, username, email, name, pw):
        u = dict(id=uuid4(), employee_id=username, role="employee", account_status="active", password_hash=pw, email=email,
                 full_name=name, can_publish=False, portal_user_id=pid)
        self.rows[username] = u; self.depts[username] = set(); self.history[u["id"]] = [dict(note="portal: created")]
        return u["id"]

    def apply_portal_role(self, uid, admin):               # mirrors UserStore.apply_portal_role (the SQL is checked on Postgres)
        u = self.get(uid)
        if admin and u["role"] not in ("system_admin", "founder_ceo"): to = "system_admin"
        elif not admin and u.get("role_set_by_portal") and u["role"] == "system_admin":
            to = u.get("role_before_portal") or "employee"
        else: return None
        frm = u["role"]; u["role"], u["role_set_by_portal"] = to, to == "system_admin"
        u["role_before_portal"] = frm if to == "system_admin" else None
        return frm, to

    def sync_portal_profile(self, uid, name, email, username):
        u = self.get(uid); u["full_name"] = name
        if email and not any(o is not u and o["email"].lower() == email for o in self.rows.values()): u["email"] = email
        if not any(o is not u and o["employee_id"].lower() == username.lower() for o in self.rows.values()):
            self.rows[username] = self.rows.pop(u["employee_id"]); self.depts[username] = self.depts.pop(u["employee_id"], set())
            u["employee_id"] = username

    def use_jti(self, jti, pid, secs):
        if jti in self.jtis: return False
        self.jtis.add(jti); return True

    def set_mfa(self, uid, enc, enabled):
        u = self.get(uid); u["mfa_secret_enc"] = enc; u["mfa_enabled_at"] = "now" if enabled else None

    def status_history(self, uid): return self.history.get(uid, [])

    def clear_portal_deactivation(self, uid): self.get(uid)["deactivated_by_portal"] = False

    def set_status(self, uid, to, actor, note=None, expect=None, by_portal=False):
        u = self.get(uid)
        matched = expect is None or u["account_status"] in expect
        u["deactivated_by_portal"] = by_portal and matched and to == "deactivated"    # mirrors UserStore.set_status
        if not matched: return None
        prev, u["account_status"] = u["account_status"], to
        self.history.setdefault(uid, []).append(dict(note=note)); return prev


class PortalOps(Ops):
    def __init__(self): super().__init__(); self.revoked_keys = []
    def revoke_user_api_keys(self, uid): self.revoked_keys.append(uid); return 1


def make(**settings):
    s = make_settings(session_secret=SECRET, portal_public_key=PUB, portal_issuer=ISS, portal_hook_secret=HOOK, **settings)
    users = PortalUsers()
    lang = LanguageService(s.roman_urdu_min_ratio)
    search = SearchService(FakeStore(vec=[cand(score=.95)]), FakeEmbedder(), None, lang, s)
    svc = Services(settings=s, users=users, knowledge=None, ops=PortalOps(), analytics=None, search=search,
                   ask=AskService(search, FakeGenerator(), s), ingestion=None, importer=None, storage=None, queue=None,
                   language=lang, embedder=FakeEmbedder(), limiter=SlidingWindowLimiter(), sessions=FakeSessions())
    svc.conversations = Chats()
    return TestClient(create_app(svc), follow_redirects=False), svc


def token(key=KEY, **over):
    now = int(time.time())
    claims = dict(iss=ISS, aud="maqsad", sub="501", jti=uuid4().hex, iat=now, exp=now + 60, username="sara.k", name="Sara K",
                  email="sara@portal.test", ip="testclient", ua_hash=UA_HASH)
    claims = {k: v for k, v in {**claims, **over}.items() if v is not None}
    return jwt.encode(claims, key, algorithm="EdDSA", headers={"typ": "JWT"})


def handoff(c, tok, json=False):
    body = f"token={tok}".encode()
    headers = {"content-type": "application/x-www-form-urlencoded"}
    if json:
        ts = str(int(time.time()))
        headers |= {"accept": "application/json", "x-quixotic-timestamp": ts, "x-quixotic-signature": sign(HOOK, ts, body)}
    return c.post("/v1/auth/portal", content=body, headers=headers)


def reasons(svc): return [r[2].get("reason") for r in svc.ops.audit_rows if r[0] == "failed_authentication"]


def refused(r):
    assert r.status_code == 401 and r.json() == {"detail": "sign-in failed"}


def test_feature_is_off_without_a_key():
    c, svc = make(); svc.settings.portal_public_key = None
    assert handoff(c, token()).status_code == 404


def test_first_handoff_creates_an_active_employee_without_departments():
    c, svc = make()
    r = handoff(c, token())
    assert r.status_code == 303 and r.headers["location"] == "/" and "qb_session" in r.cookies
    u = svc.users.get_by_portal_id(501)
    assert (u["employee_id"], u["role"], u["account_status"], svc.users.depts["sara.k"]) == ("sara.k", "employee", "active", set())
    assert c.get("/v1/auth/me").json()["employee_id"] == "sara.k"          # the cookie works from the same computer
    assert svc.sessions.rows[r.cookies["qb_session"]]["ttl"] == 28800


def test_second_handoff_syncs_name_but_never_role():
    c, svc = make()
    handoff(c, token()); svc.users.get_by_portal_id(501)["role"] = "knowledge_admin"
    handoff(c, token(name="Sara Khan"))
    u = svc.users.get_by_portal_id(501)
    assert u["full_name"] == "Sara Khan" and u["role"] == "knowledge_admin"


def test_bad_signature_expired_wrong_aud_wrong_iss_missing_claim():
    c, svc = make()
    for tok in (token(OTHER_KEY), token(iat=int(time.time()) - 400, exp=int(time.time()) - 300), token(aud="other"),
                token(iss="https://evil.test"), token(jti=None), token(ip=None), token(exp=int(time.time()) + 3600)):
        refused(handoff(c, tok))
    assert reasons(svc) == ["bad_sig", "expired", "aud", "iss", "claims", "claims", "claims"]
    assert svc.users.get_by_portal_id(501) is None


def test_a_token_works_once_only():
    c, svc = make(); tok = token()
    assert handoff(c, tok).status_code == 303
    refused(handoff(c, tok)); assert reasons(svc) == ["replay"]


def test_suspended_and_maqsad_deactivated_are_refused_but_portal_deactivated_comes_back():
    c, svc = make(); handoff(c, token()); u = svc.users.get_by_portal_id(501)
    u["account_status"] = "suspended"; refused(handoff(c, token()))
    svc.users.set_status(u["id"], "deactivated", None, "portal: left the company"); refused(handoff(c, token()))   # the note text means nothing
    assert reasons(svc) == ["state", "state"]
    svc.users.set_status(u["id"], "deactivated", None, "portal: no longer active", by_portal=True)
    assert handoff(c, token()).status_code == 303 and u["account_status"] == "active"


def test_username_clash_with_a_different_unlinked_user_is_refused():
    c, svc = make()
    svc.users.rows["sara.k"] = dict(svc.users.rows["emp_104"], employee_id="sara.k", email="someone.else@q.ai")
    svc.users.depts["sara.k"] = set()
    refused(handoff(c, token())); assert reasons(svc) == ["clash"]
    assert svc.users.get_by_portal_id(501) is None


def test_existing_account_with_the_same_email_is_linked_and_audited():
    c, svc = make(); before = svc.users.rows["emp_104"]["id"]
    old = svc.sessions.create(before, 600, True)[0]                         # a session someone already held on that account
    assert handoff(c, token(email="a@q.ai")).status_code == 303
    assert svc.sessions.rows[old]["revoked"] and svc.ops.revoked_keys == [before]
    assert svc.users.get_by_portal_id(501)["id"] == before             # same account, now linked (and renamed to the Portal username)
    assert any(r[2].get("action") == "portal_linked" for r in svc.ops.audit_rows)


def test_session_is_refused_and_revoked_from_another_ip_or_user_agent():
    c, svc = make(); sid = handoff(c, token()).cookies["qb_session"]
    far = TestClient(create_app(svc), client=("9.9.9.9", 1)); far.cookies.set("qb_session", sid)
    assert far.get("/v1/auth/me").status_code == 401
    assert c.get("/v1/auth/me").status_code == 401                          # revoked for everyone once it was misused
    sid = handoff(c, token()).cookies["qb_session"]
    assert c.get("/v1/auth/me", headers={"user-agent": "other"}).status_code == 401
    assert c.get("/v1/auth/me").status_code == 401 and reasons(svc)[-2:] == ["binding", "binding"]


def test_password_login_and_reset_are_refused_for_a_linked_user():
    c, svc = make(); handoff(c, token()); svc.users.get_by_portal_id(501)["password_hash"] = hash_password("pw")
    assert c.post("/v1/auth/login", json={"identifier": "sara.k", "password": "pw"}).status_code == 401
    mails = []
    svc.mailer = type("M", (), {"send": lambda *a, **k: mails.append(a)})()
    svc.one_time = type("T", (), {"issue": lambda *a, **k: "t" * 20, "consume": lambda *a, **k: svc.users.get_by_portal_id(501)["id"]})()
    assert c.post("/v1/auth/password-reset", json={"identifier": "sara.k"}).status_code == 202 and not mails
    assert c.post("/v1/auth/password-reset/confirm", json={"token": "t" * 20, "new_password": "Brand-new-pw-123"}).status_code == 400


def test_admin_role_gets_mfa_setup_and_verify():
    c, svc = make(admin_mfa_required=True)
    handoff(c, token()); svc.users.get_by_portal_id(501)["role"] = "system_admin"
    assert c.get("/v1/auth/session").json()["mfa"] == "none"                # employees never need it
    r = handoff(c, token(), json=True); assert r.json()["mfa"] == "setup"
    c2 = TestClient(create_app(svc)); h = {"Authorization": "Bearer " + r.json()["token"]}
    assert c2.get("/v1/auth/session", headers=h).json()["mfa"] == "setup"
    secret = c2.get("/v1/auth/mfa/setup", headers=h).json()["secret"]
    assert c2.get("/v1/auth/me", headers=h).status_code == 401             # blocked until the code is entered
    assert c2.post("/v1/auth/mfa/enable", headers=h, json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    h2 = {"Authorization": "Bearer " + handoff(c, token(), json=True).json()["token"]}     # a later sign-in must verify
    assert c2.get("/v1/auth/session", headers=h2).json()["mfa"] == "verify"
    assert c2.get("/v1/auth/me", headers=h2).status_code == 401
    assert c2.post("/v1/auth/mfa/verify", headers=h2, json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    assert c2.get("/v1/auth/me", headers=h2).status_code == 200


def test_a_portal_bearer_cannot_read_someone_elses_chat():
    c, svc = make()
    other = svc.conversations.create(svc.users.rows["emp_104"]["id"], "private", "ask", None)
    tok = handoff(c, token(), json=True).json()["token"]
    assert c.get(f"/v1/chats/{other}", headers={"Authorization": "Bearer " + tok}).status_code == 404


def _status(c, body, secret=HOOK, age=0):
    extra = f', "portal_admin": {body[2]}' if len(body) > 2 else ""
    raw = f'{{"portal_user_id": {body[0]}, "active": {body[1]}{extra}}}'.encode(); ts = str(int(time.time()) - age)
    return c.post("/v1/integrations/portal/status", content=raw, headers={"content-type": "application/json",
                  "x-quixotic-timestamp": ts, "x-quixotic-signature": sign(secret, ts, raw)})


def test_status_push_deactivates_and_revokes_live_sessions():
    c, svc = make(); sid = handoff(c, token()).cookies["qb_session"]
    assert _status(c, (501, "false")).status_code == 200
    u = svc.users.get_by_portal_id(501)
    assert u["account_status"] == "deactivated" and svc.sessions.rows[sid]["revoked"]
    assert c.get("/v1/auth/me").status_code == 401
    assert handoff(c, token()).status_code == 303                           # the Portal says active again on the next hand-off


def test_status_push_with_a_bad_or_stale_signature_is_refused():
    c, svc = make(); handoff(c, token())
    assert _status(c, (501, "false"), secret="x" * 40).status_code == 401
    assert _status(c, (501, "false"), age=1000).status_code == 401
    assert svc.users.get_by_portal_id(501)["account_status"] == "active"


def test_email_link_is_refused_for_admins_and_for_accounts_with_mfa():
    c, svc = make()
    refused(handoff(c, token(email="b@q.ai")))                              # a system admin's account
    svc.users.rows["emp_104"]["mfa_enabled_at"] = "now"
    refused(handoff(c, token(email="a@q.ai", sub="502", username="other")))  # an employee who set up two-step sign-in
    assert reasons(svc) == ["link_refused", "link_refused"]
    assert all(not u.get("portal_user_id") for u in svc.users.rows.values()) and svc.ops.revoked_keys == []


def test_mfa_passed_in_the_browser_unlocks_the_chat_panels_server_session():
    c, svc = make(admin_mfa_required=True)
    handoff(c, token()); svc.users.get_by_portal_id(501)["role"] = "system_admin"
    b1 = handoff(c, token()); secret = c.get("/v1/auth/mfa/setup").json()["secret"]
    csrf = {"x-csrf-token": b1.cookies["qb_csrf"]}
    assert c.post("/v1/auth/mfa/enable", headers=csrf, json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    server = {"Authorization": "Bearer " + handoff(c, token(), json=True).json()["token"]}
    other = TestClient(create_app(svc))
    r = other.get("/v1/auth/me", headers=server); assert r.status_code == 401 and r.json()["detail"] == "mfa_required"
    b2 = handoff(c, token())
    assert c.post("/v1/auth/mfa/verify", headers={"x-csrf-token": b2.cookies["qb_csrf"]},
                  json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    assert other.get("/v1/auth/me", headers=server).status_code == 200


def test_an_admin_deactivation_is_never_undone_by_a_handoff():
    c, svc = make(); handoff(c, token()); u = svc.users.get_by_portal_id(501)
    admin = {"Authorization": "Bearer " + svc.sessions.create(svc.users.rows["emp_9"]["id"], 600, True)[0]}
    assert _status(c, (501, "false")).status_code == 200 and u["deactivated_by_portal"]
    # the admin deactivates the already-deactivated account: refused as a transition, but the Portal's claim on it is gone
    assert c.post(f"/v1/admin/users/{u['id']}/status", headers=admin, json={"status": "deactivated"}).status_code == 409
    assert not u["deactivated_by_portal"]
    refused(handoff(c, token())); assert reasons(svc)[-1] == "state"
    svc.users.set_status(u["id"], "deactivated", None, "portal: no longer active", by_portal=True)   # Portal again...
    svc.users.set_status(u["id"], "deactivated", None, "admin", expect={"deactivated"})              # ...then any other change
    refused(handoff(c, token()))


def test_a_unique_clash_while_linking_or_syncing_is_not_a_crash():
    import contextlib
    import psycopg.errors
    from backend.database.users import UserStore

    def execute(self, sql, *a):
        if "full_name" not in sql:                       # the name is not unique; every unique column clashes
            raise psycopg.errors.UniqueViolation("dup")

    class Pool:
        @contextlib.contextmanager
        def connection(self):
            yield type("C", (), {"execute": execute})()

    store = UserStore(Pool(), "quixotic")
    assert store.link_portal(uuid4(), 501) is False
    store.sync_portal_profile(uuid4(), "Sara K", "sara@portal.test", "sara.k")     # email and username clashes are skipped


def _role_audit(svc): return [r[2] for r in svc.ops.audit_rows if r[2].get("action") == "portal_role_set"]


def test_an_admin_claim_makes_a_system_admin_with_two_step_setup_and_an_audit_row():
    c, svc = make(admin_mfa_required=True)
    r = handoff(c, token(portal_admin=True), json=True)
    u = svc.users.get_by_portal_id(501)
    assert u["role"] == "system_admin" and u["role_set_by_portal"] is True and r.json()["mfa"] == "setup"
    assert _role_audit(svc)[0]["from_role"] == "employee" and _role_audit(svc)[0]["to_role"] == "system_admin"
    assert svc.users.depts[u["employee_id"]] == set()                          # departments untouched


def test_a_later_non_admin_claim_lowers_what_the_portal_gave():
    c, svc = make()
    handoff(c, token(portal_admin=True)); handoff(c, token(portal_admin=False))
    u = svc.users.get_by_portal_id(501)
    assert u["role"] == "employee" and u["role_set_by_portal"] is False and _role_audit(svc)[-1]["to_role"] == "employee"


def test_a_hand_set_role_and_founder_ceo_are_never_changed():
    c, svc = make()
    handoff(c, token()); u = svc.users.get_by_portal_id(501)
    u["role"] = "knowledge_admin"                                              # set by a Maqsad admin: flag stays false
    handoff(c, token(portal_admin=False)); assert u["role"] == "knowledge_admin"
    handoff(c, token(portal_admin=True)); assert u["role"] == "system_admin"  # a hand demotion does not stop the Portal's rule
    assert u["role_before_portal"] == "knowledge_admin"
    u["role"], u["role_set_by_portal"] = "founder_ceo", True
    handoff(c, token(portal_admin=False)); assert u["role"] == "founder_ceo"
    handoff(c, token(portal_admin=True)); assert u["role"] == "founder_ceo"


def test_a_missing_claim_counts_as_not_admin():
    c, svc = make()
    handoff(c, token(portal_admin=True)); handoff(c, token())              # an old token without the claim
    assert svc.users.get_by_portal_id(501)["role"] == "employee"


def test_a_manual_role_change_clears_the_flag():
    import contextlib
    from backend.database.users import UserStore
    from backend.permissions.roles import Role
    seen = []

    class Pool:
        @contextlib.contextmanager
        def connection(self):
            c = type("C", (), {"execute": lambda self, sql, *a: seen.append(sql),
                               "transaction": contextlib.contextmanager(lambda self: (yield))})()
            yield c

    UserStore(Pool(), "quixotic").update_user(uuid4(), Role.KNOWLEDGE_ADMIN)
    assert any("role=%s" in q and "role_set_by_portal=false" in q for q in seen)


def test_only_a_boolean_true_claim_is_admin():
    c, svc = make()
    for v in ("true", 1, "admin", False, None):
        handoff(c, token(portal_admin=v, jti=uuid4().hex)); assert svc.users.get_by_portal_id(501)["role"] == "employee", v
    assert not _role_audit(svc)
    handoff(c, token(portal_role="admin")); assert svc.users.get_by_portal_id(501)["role"] == "employee"   # the name alone is not enough


def test_a_role_change_ends_sessions_and_api_keys_and_refreshes_the_vault(monkeypatch):
    import backend.knowledge.vault_sync as vs
    seen = []; monkeypatch.setattr(vs, "queue_refresh_for_user", lambda svc, uid, actor=None: seen.append((uid, actor)))
    c, svc = make(admin_mfa_required=True)
    sid = handoff(c, token()).cookies["qb_session"]
    handoff(c, token(portal_admin=True))                                     # raise
    u = svc.users.get_by_portal_id(501)
    assert svc.sessions.rows[sid]["revoked"] and svc.ops.revoked_keys == [u["id"]] and seen == [(u["id"], None)]
    handoff(c, token(portal_admin=False))                                    # lower
    assert svc.ops.revoked_keys == [u["id"]] * 2 and len(seen) == 2


def test_lowering_gives_back_the_role_the_person_had_before():
    c, svc = make()
    handoff(c, token()); u = svc.users.get_by_portal_id(501); u["role"] = "department_reviewer"
    handoff(c, token(portal_admin=True)); assert u["role"] == "system_admin" and u["role_before_portal"] == "department_reviewer"
    handoff(c, token(portal_admin=False))
    assert u["role"] == "department_reviewer" and u["role_before_portal"] is None and u["role_set_by_portal"] is False


def test_status_push_lowers_a_deactivated_admin_and_a_demoted_active_one():
    c, svc = make(); handoff(c, token(portal_admin=True)); u = svc.users.get_by_portal_id(501)
    sid = handoff(c, token(portal_admin=True)).cookies["qb_session"]
    assert _status(c, (501, "true", "false")).status_code == 200            # demoted, still active
    assert u["role"] == "employee" and u["account_status"] == "active" and svc.sessions.rows[sid]["revoked"]
    handoff(c, token(portal_admin=True)); assert u["role"] == "system_admin"
    assert _status(c, (501, "false", "true")).status_code == 200            # deactivated: lowered even though the flag says admin
    assert u["role"] == "employee" and u["account_status"] == "deactivated"
    assert _status(c, (501, "true")).status_code == 200 and u["role"] == "employee"   # missing portal_admin = false
    assert _status(c, (501, "true", "true")).status_code == 200 and u["role"] == "system_admin"


def test_the_portal_role_update_is_limited_to_the_tenant():
    import contextlib
    from backend.database.users import UserStore
    seen = []

    class Pool:
        @contextlib.contextmanager
        def connection(self):
            def ex(self_, sql, *a):
                seen.append(sql)
                return type("R", (), {"fetchone": lambda s: dict(role="employee", role_set_by_portal=False, role_before_portal=None)})()
            yield type("C", (), {"execute": ex, "transaction": contextlib.contextmanager(lambda self: (yield))})()

    UserStore(Pool(), "quixotic").apply_portal_role(uuid4(), True)
    UserStore(Pool(), "quixotic").sync_portal_profile(uuid4(), "N", None, "")
    assert all("tenant_id" in q for q in seen if q.lstrip().startswith("UPDATE"))
