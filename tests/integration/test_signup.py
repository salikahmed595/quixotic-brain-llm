"""PRD §5 accounts and §13 AT-01 / AT-02 on a real PostgreSQL: sign-up -> verify email -> Pending -> blocked -> admin approves ->
access; rejection and suspension revoke sessions; password reset; admin MFA; department isolation."""
import re
from uuid import UUID

import pyotp

from backend.api.v1 import auth as auth_api
from backend.auth.security import hash_password
from backend.permissions.roles import Role
from tests.integration.test_e2e import login, publish_doc, stack  # noqa: F401  (fixture)
from workers.worker import run_once

SIGNUP = {"full_name": "Nadia Khan", "username": "nadia.khan", "email": "nadia@q.ai", "password": "Secret-123"}


def _setup(stack):
    svc, client = stack
    for lim in (auth_api.signup_limiter, auth_api.attempt_limiter, auth_api.mail_limiter):
        lim._hits.clear()
    auth_api.throttle._fails.clear()
    d = lambda n: svc.users.department_by_name(n)["id"]
    svc.users.create_user("sg_admin", "sg_admin@q.ai", "Admin", hash_password("pw12345"), Role.SYSTEM_ADMIN, [])
    return svc, client, d


def _last_link(svc, kind: str) -> str:
    """The token from the newest email of this kind (console mail backend)."""
    text = [t for _, _, t in svc.mailer.sent if f"#/{kind}?token=" in t][-1]
    return re.search(rf"#/{kind}\?token=([\w-]+)", text).group(1)


def _register(client, d, **over):
    return client.post("/v1/auth/register", json={**SIGNUP, "department_id": str(d("Sales")), **over})


def test_at01_signup_verify_pending_blocked_then_approved(stack):
    svc, client, d = _setup(stack)
    r = _register(client, d)
    assert r.status_code == 201 and r.json() == {"status": "pending", "email_verification": "sent"}
    # Pending: cannot sign in, so cannot reach chat, knowledge, admin APIs or indexed content (FR-AUTH-03)
    r = client.post("/v1/auth/login", json={"identifier": "nadia.khan", "password": "Secret-123"})
    assert r.status_code == 403 and "verify your email" in r.json()["detail"]
    admin = login(client, "sg_admin")
    req = client.get("/v1/admin/access-requests", headers=admin).json()["requests"][0]
    assert req["username"] == "nadia.khan" and req["email_verified"] is False and req["requested_department"] == "Sales"
    body = {"role": "employee", "department_ids": [str(d("Sales"))]}
    assert client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=admin, json=body).status_code == 409   # not verified yet

    assert client.post("/v1/auth/verify-email", json={"token": _last_link(svc, "verify")}).json()["account_status"] == "pending"
    assert client.post("/v1/auth/verify-email", json={"token": _last_link(svc, "verify")}).status_code == 400          # once only
    r = client.post("/v1/auth/login", json={"identifier": "nadia.khan", "password": "Secret-123"})
    assert r.status_code == 403 and "waiting for approval" in r.json()["detail"]                                      # verified != approved

    r = client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=admin, json={**body, "note": "checked with HR"})
    assert r.status_code == 200
    assert client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=admin, json=body).status_code == 404  # decided
    h = login(client, "nadia.khan", "Secret-123")
    me = client.get("/v1/auth/me", headers=h).json()
    assert me["role"] == "employee" and me["account_status"] == "active" and me["company_wide"] is False
    assert [x["name"] for x in me["scope"]] == ["Sales"]                                    # FR-CHAT-06: only permitted scopes
    assert "manage_users" not in me["permissions"] and "ask" in me["permissions"]
    assert client.get("/v1/admin/users", headers=h).status_code == 403                      # no admin API for employees (§3)
    history = [x["to_status"] for x in client.get("/v1/auth/status-history", headers=h).json()["history"]]
    assert history == ["pending", "active"]                                                 # FR-AUTH-07
    assert any("approved" in subj for _, subj, _ in svc.mailer.sent)


def test_signup_validation_and_no_role_self_selection(stack):
    svc, client, d = _setup(stack)
    assert _register(client, d).status_code == 201
    assert _register(client, d, email="other@q.ai").status_code == 409                      # username taken
    assert _register(client, d, username="someone").status_code == 409                       # email taken
    assert _register(client, d, username="Bad Name!", email="y@q.ai").status_code == 422
    assert _register(client, d, username="okname", email="not-an-email").status_code == 422
    assert _register(client, d, username="okname", email="z@q.ai", password="short").status_code == 422
    assert _register(client, d, username="okname", email="z@q.ai", password="okname-2026").status_code == 422   # contains username
    assert _register(client, d, username="okname", email="z@q.ai", department_id=str(UUID(int=1))).status_code == 422
    assert client.post("/v1/auth/register", json={**SIGNUP, "username": "okname", "email": "z@q.ai"}).status_code == 422   # dept required
    r = _register(client, d, username="sneaky", email="s@q.ai", role="system_admin", phone="+92 300 1234567")
    assert r.status_code == 201 and svc.users.get_by_login("sneaky")["role"] == "employee"    # FR-AUTH-01 no self-selected role
    opts = client.get("/v1/auth/signup-options").json()["departments"]
    assert "Finance" in {x["name"] for x in opts} and set(opts[0]) == {"id", "name"}           # public: names only


def test_signups_are_rate_limited_per_address(stack):
    svc, client, d = _setup(stack)
    codes = [_register(client, d, username=f"user{i}", email=f"u{i}@q.ai").status_code for i in range(7)]
    assert codes[:5] == [201] * 5 and codes[5:] == [429, 429]


def test_at02_reject_and_suspend_revoke_access(stack):
    svc, client, d = _setup(stack)
    _register(client, d)
    client.post("/v1/auth/verify-email", json={"token": _last_link(svc, "verify")})
    admin = login(client, "sg_admin")
    rid = client.get("/v1/admin/access-requests", headers=admin).json()["requests"][0]["id"]
    assert client.post(f"/v1/admin/access-requests/{rid}/reject", headers=admin, json={"note": "not an employee"}).status_code == 200
    r = client.post("/v1/auth/login", json={"identifier": "nadia.khan", "password": "Secret-123"})
    assert r.status_code == 403 and "not approved" in r.json()["detail"]                    # told to contact an administrator

    uid = svc.users.create_user("sg_emp", "sg_emp@q.ai", "Emp", hash_password("pw12345"), Role.EMPLOYEE, [d("Sales")])
    h1, h2 = login(client, "sg_emp"), login(client, "sg_emp")                               # two devices
    assert client.get("/v1/conversations", headers=h1).status_code == 200
    r = client.post(f"/v1/admin/users/{uid}/status", headers=admin, json={"status": "suspended", "note": "investigation"})
    assert r.status_code == 200 and r.json()["sessions_revoked"] == 2
    for h in (h1, h2):                                                                       # every session ends at once
        assert client.get("/v1/conversations", headers=h).status_code == 401
        assert client.get("/v1/auth/me", headers=h).status_code == 401
        assert client.post("/v1/search", headers=h, json={"question": "x"}).status_code == 401
    assert client.post("/v1/auth/login", json={"identifier": "sg_emp", "password": "pw12345"}).status_code == 403
    assert client.post(f"/v1/admin/users/{uid}/status", headers=admin, json={"status": "active"}).status_code == 200
    assert client.get("/v1/auth/me", headers=login(client, "sg_emp")).status_code == 200
    admin_id = svc.users.get_by_login("sg_admin")["id"]
    assert client.post(f"/v1/admin/users/{admin_id}/status", headers=admin, json={"status": "suspended"}).status_code == 403
    detail = client.get(f"/v1/admin/users/{uid}", headers=admin).json()
    assert [x["to_status"] for x in detail["status_history"]] == ["active", "suspended", "active"] and detail["audit"]


def test_logout_password_reset_and_csrf(stack):
    svc, client, d = _setup(stack)
    uid = svc.users.create_user("sg_emp", "sg_emp@q.ai", "Emp", hash_password("pw12345"), Role.EMPLOYEE, [d("Sales")])
    # browser flow: cookie + CSRF header for writes
    r = client.post("/v1/auth/login", json={"identifier": "sg_emp", "password": "pw12345"})
    csrf = r.json()["csrf_token"]
    assert client.get("/v1/auth/me").status_code == 200
    assert client.post("/v1/auth/logout").status_code == 403                                 # cookie write without CSRF token
    assert client.post("/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/v1/auth/me").status_code == 401
    client.cookies.clear()
    other = login(client, "sg_emp")
    assert client.post("/v1/auth/password-reset", json={"identifier": "nobody@q.ai"}).status_code == 202   # no enumeration
    assert client.post("/v1/auth/password-reset", json={"identifier": "sg_emp@q.ai"}).status_code == 202
    token = _last_link(svc, "reset")
    assert client.post("/v1/auth/password-reset/confirm", json={"token": token, "new_password": "x" * 3}).status_code == 422
    assert client.post("/v1/auth/password-reset/confirm", json={"token": token, "new_password": "Brand-new-77"}).status_code == 200
    assert client.get("/v1/auth/me", headers=other).status_code == 401                       # reset ends every session
    assert client.post("/v1/auth/password-reset/confirm", json={"token": token, "new_password": "Brand-new-88"}).status_code == 400
    assert client.post("/v1/auth/login", json={"identifier": "sg_emp", "password": "pw12345"}).status_code == 401
    assert login(client, "sg_emp", "Brand-new-77")
    assert svc.users.get(uid)["password_hash"].startswith("$argon2id$")


def test_admin_mfa_setup_and_verify(stack):
    svc, client, d = _setup(stack)
    svc.settings = svc.settings.model_copy(update={"admin_mfa_required": True})
    h = login(client, "sg_admin")
    assert client.get("/v1/admin/users", headers=h).json()["detail"] == "mfa_required"      # nothing works before MFA
    assert client.get("/v1/auth/session", headers=h).json()["mfa"] == "setup"
    setup = client.get("/v1/auth/mfa/setup", headers=h).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/") and setup["qr_svg"].startswith("data:image/svg+xml;base64,")
    assert svc.users.get_by_login("sg_admin")["mfa_secret_enc"] != setup["secret"]           # encrypted at rest (§10)
    assert client.post("/v1/auth/mfa/enable", headers=h, json={"code": "000000"}).status_code == 401
    assert client.post("/v1/auth/mfa/enable", headers=h, json={"code": pyotp.TOTP(setup["secret"]).now()}).status_code == 200
    assert client.get("/v1/admin/users", headers=h).status_code == 200
    h2 = login(client, "sg_admin")                                                            # a new sign-in asks for the code
    assert client.get("/v1/auth/session", headers=h2).json()["mfa"] == "verify"
    assert client.get("/v1/admin/users", headers=h2).status_code == 401
    assert client.post("/v1/auth/mfa/verify", headers=h2, json={"code": pyotp.TOTP(setup["secret"]).now()}).status_code == 200
    assert client.get("/v1/admin/users", headers=h2).status_code == 200
    # employees never need MFA
    svc.users.create_user("sg_emp", "sg_emp@q.ai", "Emp", hash_password("pw12345"), Role.EMPLOYEE, [d("Sales")])
    assert client.get("/v1/auth/me", headers=login(client, "sg_emp")).status_code == 200


def _publish(svc, client, admin, title, text, dept_id):
    publish_doc(svc, client, admin, title, text, dept_id)


def test_finance_and_employee_knowledge_never_cross(stack):
    svc, client, d = _setup(stack)
    admin = login(client, "sg_admin")
    client.post("/v1/admin/departments", headers=admin, json={"name": "Employees"})
    emp_dept = svc.users.department_by_name("Employees")["id"]
    fin = d("Finance")
    _publish(svc, client, admin, "Payroll and salary run", "# Payroll\nEmployee salaries and payroll are processed by Finance on the 25th of each month. Bonus tax rules apply.", fin)
    _publish(svc, client, admin, "Employee leave guide", "# Leave\nEvery employee gets 20 days of annual leave. Request leave from your team lead.", emp_dept)
    while run_once(svc, wait_seconds=0):
        pass
    svc.users.create_user("fin_user", "fin@q.ai", "Fiona Finance", hash_password("pw12345"), Role.EMPLOYEE, [fin])
    svc.users.create_user("emp_user", "emp@q.ai", "Eli Employee", hash_password("pw12345"), Role.EMPLOYEE, [emp_dept])
    f, e = login(client, "fin_user"), login(client, "emp_user")
    seen = lambda h, q: {x["source"] for x in client.post("/v1/search", headers=h, json={"question": q}).json()["results"]}
    for q in ("annual leave days", "salaries payroll bonus", "what is the policy"):
        assert "Employee leave guide" not in seen(f, q), q                          # finance never gets employee-only knowledge
        assert "Payroll and salary run" not in seen(e, q), q                        # employees never get finance-only knowledge
    assert seen(f, "salaries payroll bonus") == {"Payroll and salary run"} and seen(e, "annual leave days") == {"Employee leave guide"}
    a = client.post("/v1/ask", headers=e, json={"question": "How are salaries and payroll processed?"}).json()
    assert all(s["title"] != "Payroll and salary run" for s in a.get("sources", []))
    # an admin can still give someone both groups
    client.post("/v1/admin/users/bulk-departments", headers=admin, json={"user_ids": [str(svc.users.get_by_login("emp_user")["id"])], "add": [str(fin)]})
    assert "Payroll and salary run" in seen(e, "salaries payroll bonus")
