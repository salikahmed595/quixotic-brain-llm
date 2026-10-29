"""Client Brain S2: /v1/clients API through the real routes, sessions and PostgreSQL. Server-side department scope on every
call (owner default: department-wide), actor recorded on every change. docs/CLIENT_BRAIN_GAP_ANALYSIS.md."""
from backend.auth.security import hash_password
from backend.database.client_memory import ClientMemoryStore
from backend.permissions.roles import Role
from tests.integration.test_e2e import login, stack  # noqa: F401  (fixture)


def _setup(stack):
    svc, client = stack
    svc.clients = ClientMemoryStore(svc.pool, svc.settings.tenant_id)
    sales = svc.users.department_by_name("Sales")["id"]
    finance = svc.users.department_by_name("Finance")["id"]
    svc.users.create_user("cl_sales", "cl_sales@q.ai", "Sam Sales", hash_password("pw12345"), Role.EMPLOYEE, [sales])
    svc.users.create_user("cl_fin", "cl_fin@q.ai", "Fay Finance", hash_password("pw12345"), Role.EMPLOYEE, [finance])
    svc.users.create_user("cl_admin", "cl_admin@q.ai", "Admin", hash_password("pw12345"), Role.SYSTEM_ADMIN, [])
    return svc, client


BUDGET = {"category": "budget", "statement": "Banner budget is $70", "value": "$70", "status": "confirmed",
          "source_type": "discord_message", "source_text": "bro can u do the purple banner for $70", "order_ref": "banner-1"}


def test_employee_creates_a_client_and_records_facts_in_their_department(stack):
    svc, client = _setup(stack)
    h = login(client, "cl_sales")
    r = client.post("/v1/clients", headers=h, json={"display_name": "NightOwl", "discord_handle": "nightowl#0001"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["department"] == "Sales"                          # the employee's only department is the default
    old = client.post(f"/v1/clients/{cid}/memories", headers=h, json=BUDGET | {"value": "$300", "statement": "Budget $300"})
    assert old.status_code == 201
    assert client.post(f"/v1/clients/{cid}/memories", headers=h, json=BUDGET).status_code == 201
    view = client.get(f"/v1/clients/{cid}", headers=h, params={"order_ref": "banner-1"}).json()
    assert view["client"]["display_name"] == "NightOwl"
    assert [(f["value"], f["status"], f["source_text"]) for f in view["facts"]] == [("$70", "confirmed", BUDGET["source_text"])]
    hist = client.get(f"/v1/clients/{cid}/history", headers=h).json()
    assert {m["value"] for m in hist["memories"]} == {"$300", "$70"}
    assert [e["event"] for e in hist["events"]].count("superseded") == 1
    assert all(e["actor"] for e in hist["events"])                     # who did it is recorded on every change
    assert [c["display_name"] for c in client.get("/v1/clients", headers=h, params={"q": "night"}).json()["clients"]] == ["NightOwl"]


def test_bad_or_guessed_facts_get_a_clear_422(stack):
    svc, client = _setup(stack)
    h = login(client, "cl_sales")
    cid = client.post("/v1/clients", headers=h, json={"display_name": "Rex"}).json()["id"]
    r = client.post(f"/v1/clients/{cid}/memories", headers=h, json=BUDGET | {"source_text": "", "source_id": ""})
    assert r.status_code == 422 and "source" in r.json()["detail"]
    r = client.post(f"/v1/clients/{cid}/memories", headers=h, json=BUDGET | {"category": "other", "statement": "client is rich"})
    assert r.status_code == 422 and "not stored" in r.json()["detail"]
    dup = client.post("/v1/clients", headers=h, json={"display_name": "A", "discord_handle": "x#1"})
    assert dup.status_code == 201
    assert client.post("/v1/clients", headers=h, json={"display_name": "B", "discord_handle": "X#1"}).status_code == 409


def test_other_departments_get_404_for_everything(stack):
    svc, client = _setup(stack)
    hs, hf = login(client, "cl_sales"), login(client, "cl_fin")
    cid = client.post("/v1/clients", headers=hs, json={"display_name": "Kitsu"}).json()["id"]
    mid = client.post(f"/v1/clients/{cid}/memories", headers=hs, json=BUDGET).json()["id"]
    for method, url in (("get", f"/v1/clients/{cid}"), ("get", f"/v1/clients/{cid}/history"),
                        ("post", f"/v1/clients/memories/{mid}/confirm"), ("delete", f"/v1/clients/memories/{mid}")):
        assert getattr(client, method)(url, headers=hf).status_code == 404, url
    assert client.post(f"/v1/clients/{cid}/memories", headers=hf, json=BUDGET).status_code == 404
    assert client.get("/v1/clients", headers=hf, params={"q": "kitsu"}).json()["clients"] == []
    assert client.post("/v1/clients", headers=hs, json={"display_name": "Z", "department": "Finance"}).status_code == 403
    assert client.get(f"/v1/clients/{cid}", headers=login(client, "cl_admin")).status_code == 200    # administrators: all


def test_confirm_and_delete(stack):
    svc, client = _setup(stack)
    h = login(client, "cl_sales")
    cid = client.post("/v1/clients", headers=h, json={"display_name": "Rex"}).json()["id"]
    mid = client.post(f"/v1/clients/{cid}/memories", headers=h, json=BUDGET | {"status": "tentative"}).json()["id"]
    assert client.post(f"/v1/clients/memories/{mid}/confirm", headers=h).status_code == 204
    assert client.get(f"/v1/clients/{cid}", headers=h, params={"order_ref": "banner-1"}).json()["facts"][0]["status"] == "confirmed"
    assert client.delete(f"/v1/clients/memories/{mid}", headers=h).status_code == 204
    assert client.get(f"/v1/clients/{cid}", headers=h).json()["facts"] == []


def test_signed_out_and_unknown_ids(stack):
    svc, client = _setup(stack)
    assert client.get("/v1/clients").status_code == 401
    h = login(client, "cl_sales")
    assert client.get("/v1/clients/00000000-0000-0000-0000-000000000000", headers=h).status_code == 404
