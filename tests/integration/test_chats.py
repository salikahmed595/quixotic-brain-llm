"""M5 on a real PostgreSQL: PRD §6 FR-CHAT-01 (persistence, rename, delete, search own titles and messages), FR-CHAT-09 (only your
own chats), §11 chat contract."""
from backend.auth.security import hash_password
from backend.permissions.roles import Role
from tests.integration.test_e2e import login, publish_doc, stack  # noqa: F401  (fixture)

DOC = "# Refunds\n## Timeline\nApproved refunds reach the customer within 7 working days."


def test_chat_contract_search_and_isolation(stack):
    svc, client = stack
    sales = svc.users.department_by_name("Sales")["id"]
    svc.users.create_user("c_admin", "c_admin@q.ai", "Admin", hash_password("pw12345"), Role.SYSTEM_ADMIN, [])
    svc.users.create_user("c_a", "c_a@q.ai", "Ann", hash_password("pw12345"), Role.EMPLOYEE, [sales])
    svc.users.create_user("c_b", "c_b@q.ai", "Ben", hash_password("pw12345"), Role.EMPLOYEE, [sales])
    publish_doc(svc, client, login(client, "c_admin"), "Refund timeline", DOC, sales)
    a, b = login(client, "c_a"), login(client, "c_b")

    chat = client.post("/v1/chats", headers=a, json={}).json()
    assert chat["title"] == "New chat"
    r = client.post(f"/v1/chats/{chat['id']}/messages", headers=a, json={"content": "How long do approved refunds take?"})
    assert r.status_code == 200 and r.json()["conversation_id"] == chat["id"] and r.json()["sources"]
    r = client.post(f"/v1/chats/{chat['id']}/messages", headers=a, json={"content": "refund timeline", "mode": "search"})
    assert r.status_code == 200 and r.json()["results"]
    got = client.get(f"/v1/chats/{chat['id']}", headers=a).json()
    assert got["title"] == "How long do approved refunds take?" and len(got["messages"]) == 4      # first question names it
    other = client.post("/v1/ask", headers=a, json={"question": "What is the greeting script?"}).json()["conversation_id"]

    # search own titles and message text (answers included)
    assert [c["id"] for c in client.get("/v1/chats?q=approved refunds", headers=a).json()["chats"]] == [chat["id"]]
    found = client.get("/v1/chats?q=7 working days", headers=a).json()["chats"]
    assert [c["id"] for c in found] == [chat["id"]] and "7 working days" in found[0]["snippet"]
    assert {c["id"] for c in client.get("/v1/chats", headers=a).json()["chats"]} == {chat["id"], other}
    assert client.get("/v1/chats?q=%", headers=a).json()["chats"] == []                         # wildcards are not special

    # FR-CHAT-09: B can never read, search, post to, rename or delete A's chats
    assert client.get("/v1/chats", headers=b).json()["chats"] == []
    assert client.get("/v1/chats?q=refunds", headers=b).json()["chats"] == []
    assert client.get(f"/v1/chats/{chat['id']}", headers=b).status_code == 404
    assert client.post(f"/v1/chats/{chat['id']}/messages", headers=b, json={"content": "hi"}).status_code == 404
    assert client.post("/v1/ask", headers=b, json={"question": "hi", "conversation_id": chat["id"]}).status_code == 404
    assert client.patch(f"/v1/chats/{chat['id']}", headers=b, json={"title": "mine"}).status_code == 404
    assert client.delete(f"/v1/chats/{chat['id']}", headers=b).status_code == 404
    assert client.delete("/v1/chats", headers=b).json() == {"deleted": 0}
    # even an administrator cannot open someone's chat through the chat API (aggregate analytics only)
    assert client.get(f"/v1/chats/{chat['id']}", headers=login(client, "c_admin")).status_code == 404

    assert client.patch(f"/v1/chats/{chat['id']}", headers=a, json={"title": "  Refunds  "}).json()["title"] == "Refunds"
    assert client.delete(f"/v1/chats/{chat['id']}", headers=a).status_code == 204
    assert client.get(f"/v1/chats/{chat['id']}", headers=a).status_code == 404
