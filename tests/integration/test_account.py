"""Profile picture, personalization, password change, chat memory and bulk department access (owner request 2026-10-05)."""
import base64

import pytest

from backend.auth.security import hash_password
from backend.database.conversations import ConversationStore
from backend.permissions.roles import Role
from tests.integration.test_e2e import login, stack  # noqa: F401  (fixture)

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()


def _setup(stack):
    svc, client = stack
    svc.conversations = ConversationStore(svc.pool, svc.settings.tenant_id)
    sales = svc.users.department_by_name("Sales")["id"]
    finance = svc.users.department_by_name("Finance")["id"]
    admin = svc.users.create_user("ac_admin", "ac_admin@q.ai", "Admin", hash_password("pw12345"), Role.ADMINISTRATOR, [])
    mgr = svc.users.create_user("ac_mgr", "ac_mgr@q.ai", "Mona Manager", hash_password("pw12345"), Role.MANAGER, [sales, finance])
    return svc, client, sales, finance, admin, mgr


def test_profile_picture_and_name(stack):
    svc, client, *_ = _setup(stack)
    h = login(client, "ac_mgr")
    assert client.get("/v1/auth/me", headers=h).json()["avatar"] is None
    r = client.patch("/v1/auth/profile", headers=h, json={"full_name": "  Mona   M  ", "avatar": PNG})
    assert r.status_code == 200 and r.json()["avatar"] == PNG and r.json()["full_name"] == "Mona M"
    for bad in ("data:image/svg+xml;base64,PHN2Zz4=", "data:text/html;base64,PGI+", "https://x/y.png", PNG[:30] + "!!notbase64!!",
                "data:image/png;base64," + "A" * 400_000):
        assert client.patch("/v1/auth/profile", headers=h, json={"avatar": bad}).status_code == 422, bad[:40]
    assert client.patch("/v1/auth/profile", headers=h, json={"full_name": "   "}).status_code == 422
    assert client.patch("/v1/auth/profile", headers=h, json={"avatar": ""}).json()["avatar"] is None     # remove


def test_preferences_are_cleaned_and_reach_the_answer_model_with_the_role(stack):
    svc, client, sales, finance, *_ = _setup(stack)
    h = login(client, "ac_mgr")
    saved = client.put("/v1/auth/preferences", headers=h, json={"answer_style": "concise", "tone": "NOT-A-TONE", "language": "roman_urdu",
                                                                  "about_me": "I lead  the Karachi team", "instructions": "x" * 10}).json()
    assert saved["answer_style"] == "concise" and saved["tone"] == "professional" and saved["language"] == "roman_urdu"
    assert saved["about_me"] == "I lead the Karachi team"
    assert client.put("/v1/auth/preferences", headers=h, json={"about_me": "x" * 501}).status_code == 422
    assert client.get("/v1/auth/me", headers=h).json()["preferences"]["language"] == "roman_urdu"

    admin = login(client, "ac_admin")
    client.post("/v1/knowledge", headers=admin, json={"title": "Refund rules", "department_ids": [str(sales)], "information": "Refunds take 7 days."})
    gen = svc.ask.generator
    # ask through the service directly with the same wiring the API uses
    from backend.api.v1.ask import _asker
    class C: key = None; principal = svc.users.principal(svc.users.get_by_login("ac_mgr"))
    asker, prefs = _asker(svc, C)
    assert asker == {"role": "manager", "departments": ["Finance", "Sales"]} and prefs["language"] == "roman_urdu"


def test_password_change(stack):
    svc, client, *_ = _setup(stack)
    h = login(client, "ac_mgr")
    assert client.post("/v1/auth/password", headers=h, json={"current_password": "wrong-one", "new_password": "newpass123"}).status_code == 403
    assert client.post("/v1/auth/password", headers=h, json={"current_password": "pw12345", "new_password": "short"}).status_code == 422
    assert client.post("/v1/auth/password", headers=h, json={"current_password": "pw12345", "new_password": "pw12345"}).status_code == 422
    assert client.post("/v1/auth/password", headers=h, json={"current_password": "pw12345", "new_password": "newpass123"}).status_code == 200
    assert client.post("/v1/auth/login", json={"identifier": "ac_mgr", "password": "pw12345"}).status_code == 401
    login(client, "ac_mgr", "newpass123")


def test_delete_all_my_chats_only_mine(stack):
    svc, client, sales, finance, admin_id, mgr_id = _setup(stack)
    a, m = login(client, "ac_admin"), login(client, "ac_mgr")
    svc.conversations.create(admin_id, "admin chat", "general", None)
    svc.conversations.create(mgr_id, "mgr chat 1", "general", None)
    svc.conversations.create(mgr_id, "mgr chat 2", "general", None)
    assert client.delete("/v1/conversations", headers=m).json() == {"deleted": 2}
    assert client.get("/v1/conversations", headers=m).json()["conversations"] == []
    assert len(client.get("/v1/conversations", headers=a).json()["conversations"]) == 1


def test_bulk_department_access_and_who_can_see_what(stack):
    svc, client, sales, finance, admin_id, mgr_id = _setup(stack)
    hr = svc.users.department_by_name("HR")["id"]
    ids = [svc.users.create_user(f"bulk{i}", f"bulk{i}@q.ai", f"Bulk {i}", hash_password("pw12345"), Role.EMPLOYEE, []) for i in range(3)]
    admin = login(client, "ac_admin")
    r = client.post("/v1/users/bulk-departments", headers=admin, json={"user_ids": [str(i) for i in ids], "add": [str(hr), str(sales)]})
    assert r.json() == {"updated": 3}
    users = {u["employee_id"]: set(u["departments"]) for u in client.get("/v1/users", headers=admin).json()["users"]}
    assert users["bulk0"] == {"HR", "Sales"}
    client.post("/v1/users/bulk-departments", headers=admin, json={"user_ids": [str(i) for i in ids], "remove": [str(sales)]})
    users = {u["employee_id"]: set(u["departments"]) for u in client.get("/v1/users", headers=admin).json()["users"]}
    assert users["bulk1"] == {"HR"}
    assert client.post("/v1/users/bulk-departments", headers=admin, json={"user_ids": [str(ids[0])]}).status_code == 422     # nothing to do
    emp = login(client, "bulk0")
    assert client.post("/v1/users/bulk-departments", headers=emp, json={"user_ids": [str(ids[0])], "add": [str(sales)]}).status_code == 403
