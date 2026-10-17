"""Learning from 👍 / 👎 on a real PostgreSQL: ratings -> retrieval order, personal style, chat marks, admin report, reset."""
from uuid import UUID, uuid4

from backend.auth.security import hash_password
from backend.database.conversations import ConversationStore
from backend.learning.feedback import make_signal_source
from backend.permissions.roles import Role
from tests.integration.test_e2e import login, stack  # noqa: F401  (fixture)
from workers.worker import run_once

SHORT_LIST = "- Ask about the concern\n- Explain the value\n- Offer payment options"
LONG_PROSE = " ".join(["You should begin by listening carefully to the customer and then explaining the value of the service in detail."] * 8)

DOC = b"""# Pricing Policy

## Discounts
Customers can get a discount on large price orders after manager approval. Discount price rules apply.

## Refund price
Refund price requests are reviewed against the order. Price refund rules apply to every order.

## Payment price plans
Price payment plans can be arranged for large orders. Payment price discount options exist.

## Price list
The price list shows the standard price of every service and package. Price changes need approval.
"""


def _setup(stack, n_users=6):
    svc, client = stack
    sales = svc.users.department_by_name("Sales")["id"]
    svc.users.create_user("lr_admin", "lr_admin@q.ai", "Admin", hash_password("pw12345"), Role.SYSTEM_ADMIN, [])
    users = [svc.users.create_user(f"lr_u{i}", f"lr_u{i}@q.ai", f"User {i}", hash_password("pw12345"), Role.EMPLOYEE, [sales]) for i in range(n_users)]
    return svc, client, sales, users


def _log(svc, uid, chunk_ids, answer="An answer.", confidence="high", language="english", question="price question"):
    retrieved = [{"chunk_id": str(c), "title": f"Doc {i}", "section": f"S{i}", "version": 1} for i, c in enumerate(chunk_ids)]
    return svc.ops.log_query(user_id=uid, api_key_id=None, department_id=None, mode="general", original=question, normalized=question,
                             language=language, confidence=confidence, score=0.5, found=True, retrieved=retrieved, answer=answer, latency_ms=1)


def test_votes_count_latest_rating_per_person_top_positions_only_and_reset(stack):
    svc, client, sales, users = _setup(stack, 3)
    ops = svc.ops
    first, second, third = uuid4(), uuid4(), uuid4()
    q1 = _log(svc, users[0], [first, second, third])
    ops.add_feedback(q1, users[0], True, None, None, None)
    ops.add_feedback(q1, users[0], False, None, None, None)                     # same person changes their mind: only the 👎 counts
    q2 = _log(svc, users[1], [first, second, third]); ops.add_feedback(q2, users[1], False, None, None, None)
    q3 = _log(svc, users[2], [second, first, third]); ops.add_feedback(q3, users[2], True, None, None, None)
    votes = ops.chunk_votes([first, second, third], 2)
    assert votes[first] == (1, 2) and votes[second] == (1, 2)                   # first: up from u2, down from u0 and u1; second likewise
    assert third not in votes                                                  # third place is never credited
    ops.reset_learning(None)
    assert ops.chunk_votes([first, second], 2, ops.learning_since()) == {}      # after a reset the old ratings stop counting
    q4 = _log(svc, users[0], [first]); ops.add_feedback(q4, users[0], True, None, None, None)
    assert ops.chunk_votes([first], 2, ops.learning_since()) == {first: (1, 0)}  # ...and new ones count again


def test_ratings_move_a_passage_in_the_real_search_order_and_it_can_be_switched_off(stack):
    svc, client, sales, users = _setup(stack, 6)
    admin = login(client, "lr_admin")
    client.post("/v1/documents", headers=admin, files={"file": ("pricing.md", DOC, "text/markdown")},
                data={"department_ids": str(sales), "title": "Pricing Policy", "status": "active"})
    while run_once(svc, wait_seconds=0):
        pass
    scope = frozenset({sales})
    before = svc.search.search("price discount refund", scope).candidates
    top = before[0]
    assert len(before) >= 3
    svc.search.feedback_signals = make_signal_source(svc.ops, svc.settings)
    for u in users:                                                              # six different people rate answers whose first passage was `top`
        qid = _log(svc, u, [top.chunk_id] + [c.chunk_id for c in before[1:3]])
        svc.ops.add_feedback(qid, u, False, None, None, None)
    after = [c.chunk_id for c in svc.search.search("price discount refund", scope).candidates]
    assert after.index(top.chunk_id) >= 1 and after.index(top.chunk_id) <= 4     # slipped, but still there (never hidden)
    assert set(after) >= {c.chunk_id for c in before[:3]}
    object.__setattr__(svc.settings, "feedback_learning", False)                 # the switch
    assert [c.chunk_id for c in svc.search.search("price discount refund", scope).candidates][0] == top.chunk_id


def test_personal_style_is_learned_shown_and_forgotten(stack):
    svc, client, sales, users = _setup(stack, 2)
    u = users[0]
    for _ in range(3):
        svc.ops.add_feedback(_log(svc, u, [uuid4()], answer=SHORT_LIST), u, True, None, None, None)
    for _ in range(2):
        svc.ops.add_feedback(_log(svc, u, [uuid4()], answer=LONG_PROSE), u, False, None, None, None)
    h = login(client, "lr_u0")
    got = client.get("/v1/auth/learned", headers=h).json()
    assert got["enabled"] and got["liked"] == 3 and got["disliked"] == 2
    assert "short, to-the-point answers" in got["hints"] and "bullet points or numbered steps" in got["hints"]
    other = client.get("/v1/auth/learned", headers=login(client, "lr_u1")).json()
    assert other["hints"] == [] and other["liked"] == 0                         # one person's ratings never shape another's answers
    client.put("/v1/auth/preferences", headers=h, json={"learn": False})
    assert client.get("/v1/auth/learned", headers=h).json()["enabled"] is False
    client.put("/v1/auth/preferences", headers=h, json={"learn": True})
    assert client.post("/v1/auth/learned/reset", headers=h).json() == {"reset": True}
    got = client.get("/v1/auth/learned", headers=h).json()
    assert got["hints"] == [] and got["liked"] == 0                              # forgotten


def test_a_rejected_answer_is_marked_in_the_next_question_of_the_same_chat(stack):
    svc, client, sales, users = _setup(stack, 1)
    svc.conversations = ConversationStore(svc.pool, svc.settings.tenant_id)
    admin = login(client, "lr_admin")
    client.post("/v1/documents", headers=admin, files={"file": ("pricing.md", DOC, "text/markdown")}, data={"department_ids": str(sales), "title": "Pricing Policy", "status": "active"})
    while run_once(svc, wait_seconds=0):
        pass
    h = login(client, "lr_u0")
    a1 = client.post("/v1/ask", headers=h, json={"question": "what are the price discount rules?"}).json()
    cid = a1["conversation_id"]
    client.post("/v1/ask", headers=h, json={"question": "and for refunds?", "conversation_id": cid})
    assert [x[2] for x in svc.ask.generator.calls[-1][0].history] == [None]       # nothing rated yet
    client.post("/v1/feedback", headers=h, json={"query_id": a1["query_id"], "helpful": False})
    client.post("/v1/ask", headers=h, json={"question": "explain the discount rules again", "conversation_id": cid})
    marks = [x[2] for x in svc.ask.generator.calls[-1][0].history]
    assert marks[0] == "not helpful"
    client.post("/v1/feedback", headers=h, json={"query_id": a1["query_id"], "helpful": True})     # changed their mind
    client.post("/v1/ask", headers=h, json={"question": "one more question about price", "conversation_id": cid})
    assert svc.ask.generator.calls[-1][0].history[0][2] == "helpful"


def test_admin_report_and_reset_are_admin_only_and_name_no_one(stack):
    svc, client, sales, users = _setup(stack, 4)
    for i, u in enumerate(users):
        q = _log(svc, u, [uuid4()], answer=f"answer {i}", confidence="high" if i < 3 else "medium", language="roman_urdu" if i == 0 else "english")
        svc.ops.add_feedback(q, u, i != 0 and i != 1, None, None, None)
        if i == 0:
            svc.ops.add_feedback(q, u, None, None, None, "wrong answer")
    admin = login(client, "lr_admin")
    r = client.get("/v1/answer-quality", headers=admin).json()
    assert (r["up"], r["down"]) == (2, 2) and r["learning_enabled"] is True
    conf = {x["k"]: (x["up"], x["down"]) for x in r["by_confidence"]}
    assert conf["high"] == (1, 2) and conf["medium"] == (1, 0)                     # does "high" really mean helpful?
    assert {x["k"] for x in r["by_language"]} == {"roman_urdu", "english"}
    assert r["weakest_sources"] and r["weakest_sources"][0]["down"] >= 1
    bad = r["recent_not_helpful"]
    assert len(bad) == 2 and any(b["note"] == "wrong answer" for b in bad)
    assert "user_id" not in bad[0] and "employee_id" not in bad[0]                  # the report is about answers, not people
    emp = login(client, "lr_u0")
    assert client.get("/v1/answer-quality", headers=emp).status_code == 403
    assert client.post("/v1/learning/reset", headers=emp).status_code == 403
    assert client.post("/v1/learning/reset", headers=admin).json() == {"reset": True}
    r = client.get("/v1/answer-quality", headers=admin).json()
    assert (r["up"], r["down"]) == (0, 0)                                           # ratings given before the reset no longer count
