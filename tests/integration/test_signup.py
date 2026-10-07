"""Self sign-up with approval, and department isolation (owner request 2026-10-05)."""
from uuid import UUID

from backend.api.v1 import auth as auth_api
from backend.auth.security import hash_password
from backend.permissions.roles import Role
from tests.integration.test_e2e import login, stack  # noqa: F401  (fixture)
from workers.worker import run_once

SIGNUP = {"full_name": "Nadia Khan", "username": "nadia.khan", "email": "nadia@q.ai", "password": "secret123"}


def _setup(stack):
    svc, client = stack
    auth_api.signup_limiter._hits.clear(); auth_api.attempt_limiter._hits.clear()
    d = lambda n: svc.users.department_by_name(n)["id"]
    svc.users.create_user("sg_admin", "sg_admin@q.ai", "Admin", hash_password("pw12345"), Role.ADMINISTRATOR, [])
    svc.users.create_user("sg_mgr", "sg_mgr@q.ai", "Sam Manager", hash_password("pw12345"), Role.MANAGER, [d("Sales")])
    return svc, client, d


def test_signup_is_pending_cannot_sign_in_and_validates(stack):
    svc, client, d = _setup(stack)
    assert client.post("/v1/auth/register", json=SIGNUP).json() == {"status": "pending"}
    r = client.post("/v1/auth/login", json={"identifier": "nadia.khan", "password": "secret123"})
    assert r.status_code == 403 and "waiting for approval" in r.json()["detail"]
    assert client.post("/v1/auth/login", json={"identifier": "NADIA@q.ai", "password": "secret123"}).status_code == 403    # email, any case
    assert client.post("/v1/auth/login", json={"identifier": "nadia.khan", "password": "wrong-pass"}).status_code == 401  # no hint for a wrong password
    assert client.post("/v1/auth/register", json={**SIGNUP, "email": "other@q.ai"}).status_code == 409                    # username taken
    assert client.post("/v1/auth/register", json={**SIGNUP, "username": "someone"}).status_code == 409                     # email taken
    assert client.post("/v1/auth/register", json={**SIGNUP, "username": "sg_admin", "email": "x@q.ai"}).status_code == 409  # an existing user
    assert client.post("/v1/auth/register", json={**SIGNUP, "username": "Bad Name!", "email": "y@q.ai"}).status_code == 422
    assert client.post("/v1/auth/register", json={**SIGNUP, "username": "okname", "email": "not-an-email"}).status_code == 422
    assert client.post("/v1/auth/register", json={**SIGNUP, "username": "okname", "email": "z@q.ai", "password": "short"}).status_code == 422
    assert client.post("/v1/auth/register", json={**SIGNUP, "username": "okname", "email": "z@q.ai", "department_id": str(UUID(int=1))}).status_code == 422
    assert [u["employee_id"] for u in client.get("/v1/users", headers=login(client, "sg_admin")).json()["users"] if u["employee_id"] == "nadia.khan"] == []   # not in Users yet
    opts = client.get("/v1/auth/signup-options").json()["departments"]
    assert "Finance" in {x["name"] for x in opts} and set(opts[0]) == {"id", "name"}                                         # public: names only


def test_signups_are_rate_limited_per_address(stack):
    svc, client, d = _setup(stack)
    codes = [client.post("/v1/auth/register", json={**SIGNUP, "username": f"user{i}", "email": f"u{i}@q.ai"}).status_code for i in range(7)]
    assert codes[:5] == [201] * 5 and codes[5:] == [429, 429]


def test_admin_and_manager_approval_rules(stack):
    svc, client, d = _setup(stack)
    sales, fin = str(d("Sales")), str(d("Finance"))
    for u, dept in (("asks.sales", sales), ("asks.finance", fin), ("asks.none", None)):
        client.post("/v1/auth/register", json={**SIGNUP, "username": u, "email": f"{u}@q.ai", **({"department_id": dept} if dept else {})})
    admin, mgr = login(client, "sg_admin"), login(client, "sg_mgr")
    names = lambda h: {r["username"] for r in client.get("/v1/access-requests", headers=h).json()["requests"]}
    assert names(admin) == {"asks.sales", "asks.finance", "asks.none"}
    assert names(mgr) == {"asks.sales", "asks.none"}                                  # a Sales manager does not see Finance's requests
    emp = svc.users.create_user("sg_emp", "sg_emp@q.ai", "Emp", hash_password("pw12345"), Role.EMPLOYEE, [d("Sales")])
    assert client.get("/v1/access-requests", headers=login(client, "sg_emp")).status_code == 403

    rid = {r["username"]: r["id"] for r in client.get("/v1/access-requests", headers=admin).json()["requests"]}
    approve = lambda h, user, **b: client.post(f"/v1/access-requests/{rid[user]}/approve", headers=h, json=b)
    assert approve(mgr, "asks.finance", role="employee", department_ids=[sales]).status_code == 404       # not in a manager's view
    assert approve(mgr, "asks.sales", role="manager", department_ids=[sales]).status_code == 403          # managers cannot make managers
    assert approve(mgr, "asks.sales", role="employee", department_ids=[fin]).status_code == 403           # nor grant a department they lack
    assert approve(mgr, "asks.sales", role="employee", department_ids=[]).status_code == 422              # at least one department
    assert approve(mgr, "asks.sales", role="employee", department_ids=[sales]).status_code == 200
    assert approve(mgr, "asks.sales", role="employee", department_ids=[sales]).status_code == 404         # already decided

    h = login(client, "asks.sales", "secret123")                                      # can sign in now
    me = client.get("/v1/auth/me", headers=h).json()
    assert me["role"] == "employee" and [x["name"] for x in me["departments"]] == ["Sales"]
    assert approve(admin, "asks.finance", role="contributor", department_ids=[fin, sales]).status_code == 200
    me = client.get("/v1/auth/me", headers=login(client, "asks.finance", "secret123")).json()
    assert me["role"] == "contributor" and {x["name"] for x in me["departments"]} == {"Finance", "Sales"}

    assert client.post(f"/v1/access-requests/{rid['asks.none']}/reject", headers=mgr).status_code == 200
    r = client.post("/v1/auth/login", json={"identifier": "asks.none", "password": "secret123"})
    assert r.status_code == 403 and "not approved" in r.json()["detail"]
    assert names(admin) == set()
    users = {u["employee_id"] for u in client.get("/v1/users", headers=admin).json()["users"]}
    assert {"asks.sales", "asks.finance"} <= users                                    # approved people appear in Users


def _publish(client, admin, title, text, dept_id):
    r = client.post("/v1/documents", headers=admin, files={"file": (f"{title}.md", text.encode(), "text/markdown")},
                    data={"department_ids": str(dept_id), "title": title, "status": "active"})
    assert r.status_code == 202, r.text


def test_finance_and_employee_knowledge_never_cross(stack):
    svc, client, d = _setup(stack)
    admin = login(client, "sg_admin")
    emp_dept = client.post("/v1/departments", headers=admin, json={"name": "Employees"}).json()
    emp_dept = svc.users.department_by_name("Employees")["id"]
    fin = d("Finance")
    _publish(client, admin, "Payroll and salary run", "# Payroll\nEmployee salaries and payroll are processed by Finance on the 25th of each month. Bonus tax rules apply.", fin)
    _publish(client, admin, "Employee leave guide", "# Leave\nEvery employee gets 20 days of annual leave. Request leave from your team lead.", emp_dept)
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
    client.post("/v1/users/bulk-departments", headers=admin, json={"user_ids": [str(svc.users.get_by_login("emp_user")["id"])], "add": [str(fin)]})
    assert "Payroll and salary run" in seen(e, "salaries payroll bonus")
