"""M3 on a real PostgreSQL: proposals, review rules, controlled publication with the Git vault, rollback, Obsidian import.
PRD §3, §7 (Approvals, Documents), §8, §9 steps 5–7, §12, §13 AT-06."""
import io
import zipfile
from pathlib import Path
from uuid import UUID

from backend.auth.security import hash_password
from backend.knowledge.service import KnowledgeService
from backend.knowledge.vault import VaultError
from backend.permissions.roles import Role
from tests.integration.test_e2e import drain, login, publish_doc, second_approver, stack  # noqa: F401  (fixture)

LEAVE = "# Annual leave\nFresh sellers get 14 days of annual leave in their first year."


def _setup(stack):
    svc, client = stack
    d = lambda n: svc.users.department_by_name(n)["id"]
    sales, hr = d("Sales"), d("HR")
    svc.users.create_user("k_admin", "k_admin@q.ai", "Admin", hash_password("pw12345"), Role.SYSTEM_ADMIN, [])
    ka = svc.users.create_user("k_ka", "k_ka@q.ai", "Kim Curator", hash_password("pw12345"), Role.KNOWLEDGE_ADMIN, [])
    rev = svc.users.create_user("k_rev", "k_rev@q.ai", "Rae Reviewer", hash_password("pw12345"), Role.DEPARTMENT_REVIEWER, [sales, hr])
    svc.users.update_department(sales, reviewer_ids=[rev])
    svc.users.create_user("k_emp", "k_emp@q.ai", "Eve Employee", hash_password("pw12345"), Role.EMPLOYEE, [sales])
    return svc, client, sales, hr, ka


def _propose_text(client, h, title, body, dept, **extra):
    r = client.post("/v1/knowledge/proposals", headers=h, json={"title": title, "body": body, "department_ids": [str(dept)],
                                                               "sensitivity": "internal", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_review_rules_reviewers_publishers_and_requests_for_changes(stack):
    svc, client, sales, hr, ka = _setup(stack)
    admin, kah, rev, emp = (login(client, x) for x in ("k_admin", "k_ka", "k_rev", "k_emp"))
    assert client.post("/v1/knowledge/proposals", headers=emp, json={"title": "x", "body": "y", "department_ids": [str(sales)],
                                                                     "sensitivity": "internal"}).status_code == 403   # §3 employees
    sales_doc = _propose_text(client, kah, "Fresh seller handoff", "Hand the lead to the upseller after the first order.", sales)
    hr_doc = _propose_text(client, kah, "Office hours", "The office opens at nine.", hr)
    drain(svc)
    # the reviewer reviews Sales only; their approval alone does not publish (needs a publisher, §3)
    assert client.post(f"/v1/admin/proposals/{hr_doc['proposal_id']}/approve", headers=rev, json={}).status_code == 403
    r = client.post(f"/v1/admin/proposals/{sales_doc['proposal_id']}/approve", headers=rev, json={}).json()
    assert r["status"] == "open" and "an approval by a publisher" in r["waiting_for"]
    # a Knowledge Admin without the publisher grant cannot decide at all
    assert client.post(f"/v1/admin/proposals/{hr_doc['proposal_id']}/approve", headers=kah, json={}).status_code == 403
    assert client.post(f"/v1/admin/proposals/{sales_doc['proposal_id']}/approve", headers=admin, json={}).json()["status"] == "approved"
    drain(svc)
    assert svc.knowledge.get_proposal(UUID(sales_doc["proposal_id"]))["status"] == "published"
    # queue: the reviewer sees only proposals of their departments
    seen = {p["title"] for p in client.get("/v1/knowledge/proposals", headers=rev).json()["proposals"]}
    assert "Office hours" not in seen
    # request changes needs a note, puts the version back to draft and tells the author
    assert client.post(f"/v1/admin/proposals/{hr_doc['proposal_id']}/request-changes", headers=admin, json={}).status_code == 422
    assert client.post(f"/v1/admin/proposals/{hr_doc['proposal_id']}/request-changes", headers=admin,
                       json={"note": "Add the closing time"}).json()["status"] == "changes_requested"
    assert svc.knowledge.get_version(UUID(hr_doc["version_id"]))["status"] == "draft"
    assert any("Changes requested" in subj for _, subj, _ in svc.mailer.sent)
    assert client.post(f"/v1/admin/proposals/{hr_doc['proposal_id']}/approve", headers=admin, json={}).status_code == 409
    # the author proposes again on the same document; withdraw works for open proposals only
    again = _propose_text(client, kah, "Office hours", "The office opens at nine and closes at six.", hr, item_id=hr_doc["item_id"])
    assert client.post(f"/v1/knowledge/proposals/{again['proposal_id']}/withdraw", headers=rev).status_code == 403
    assert client.post(f"/v1/knowledge/proposals/{again['proposal_id']}/withdraw", headers=kah).status_code == 200
    # employees never see the knowledge admin pages
    assert client.get("/v1/knowledge/documents", headers=emp).status_code == 403


def test_at06_update_diff_publish_and_restore_previous_version(stack):
    svc, client, sales, hr, ka = _setup(stack)
    admin, emp = login(client, "k_admin"), login(client, "k_emp")
    first = publish_doc(svc, client, admin, "Leave guide", LEAVE, sales)
    item = first["item_id"]
    upd = _propose_text(client, admin, "Leave guide", LEAVE.replace("14 days", "16 days"), sales, item_id=item,
                        sensitivity="internal", change_note="Leave increased in 2027")
    # only one open change per document
    assert client.post("/v1/knowledge/proposals", headers=admin, json={"item_id": item, "title": "Leave guide", "body": "x",
                                                                      "department_ids": [str(sales)], "sensitivity": "internal"}).status_code == 409
    drain(svc)
    view = client.get(f"/v1/knowledge/proposals/{upd['proposal_id']}", headers=admin).json()
    assert "-Fresh sellers get 14 days of annual leave in their first year." in view["diff"]["unified"]
    assert "+Fresh sellers get 16 days of annual leave in their first year." in view["diff"]["unified"]
    assert view["diff"]["before"]["version"] == 1 and view["diff"]["after"]["version"] == 2
    ask = lambda: " ".join(x["text"] for x in client.post("/v1/search", headers=emp, json={"question": "annual leave days fresh sellers"}).json()["results"])
    assert "14 days" in ask() and "16 days" not in ask()                       # unapproved change never appears (§1, AT-07 idea)
    client.post(f"/v1/admin/proposals/{upd['proposal_id']}/approve", headers=admin, json={})
    drain(svc)
    assert "16 days" in ask() and "14 days" not in ask()                       # AT-06: new version searchable
    doc = client.get(f"/v1/knowledge/documents/{item}", headers=admin).json()
    assert [(v["version"], v["status"]) for v in doc["versions"]] == [(2, "published"), (1, "archived")]
    vault_note = (Path(svc.settings.vault_dir) / doc["item"]["vault_path"]).read_text(encoding="utf-8")
    assert "16 days" in vault_note and "version: 2" in vault_note
    # old version recoverable (§2 goal 6, AT-06): restore v1 through a reviewed proposal
    v1 = next(v["id"] for v in doc["versions"] if v["version"] == 1)
    res = client.post(f"/v1/admin/documents/{item}/restore", headers=admin, json={"version_id": v1, "note": "policy reverted"}).json()
    client.post(f"/v1/admin/proposals/{res['proposal_id']}/approve", headers=admin, json={})
    drain(svc)
    assert "14 days" in ask() and "16 days" not in ask()


def test_failed_publication_keeps_the_previous_version_and_can_be_retried(stack, monkeypatch):
    svc, client, sales, hr, ka = _setup(stack)
    admin, emp = login(client, "k_admin"), login(client, "k_emp")
    item = publish_doc(svc, client, admin, "Leave guide", LEAVE, sales)["item_id"]
    upd = _propose_text(client, admin, "Leave guide", LEAVE.replace("14 days", "21 days"), sales, item_id=item)
    drain(svc)
    real = KnowledgeService._verify_retrievable
    monkeypatch.setattr(KnowledgeService, "_verify_retrievable", lambda self, vid: (_ for _ in ()).throw(VaultError("index out of sync")))
    client.post(f"/v1/admin/proposals/{upd['proposal_id']}/approve", headers=admin, json={})
    drain(svc)
    prop = svc.knowledge.get_proposal(UUID(upd["proposal_id"]))
    assert prop["status"] == "failed" and "out of sync" in prop["error"]
    text = " ".join(x["text"] for x in client.post("/v1/search", headers=emp, json={"question": "annual leave days"}).json()["results"])
    assert "14 days" in text and "21 days" not in text                         # §8 fail closed: previous version stays live
    assert any("Publication failed" in subj for _, subj, _ in svc.mailer.sent)  # §9 step 7 alert the owner
    monkeypatch.setattr(KnowledgeService, "_verify_retrievable", real)
    assert client.post(f"/v1/admin/proposals/{upd['proposal_id']}/retry", headers=admin).status_code == 202
    drain(svc)
    assert svc.knowledge.get_proposal(UUID(upd["proposal_id"]))["status"] == "published"


def test_obsidian_import_front_matter_and_approval(stack):
    svc, client, sales, hr, ka = _setup(stack)
    admin = login(client, "k_admin")
    note = "---\ntitle: Upsell script\ndepartments: [Sales]\nsensitivity: internal\ncategory: Scripts\nsource: Sales playbook 2026\n---\n\n# Upsell\nOffer framing after the first artwork.\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Sales/Upsell script.md", note)
        z.writestr(".obsidian/app.json", "{}")
        z.writestr("Archive/old.md", "# old")
    r = client.post("/v1/admin/documents/import-obsidian", headers=admin, files={"files": ("vault.zip", buf.getvalue(), "application/zip")},
                    data={"approve": "true"})
    assert r.status_code == 202, r.text
    res = r.json()["results"]
    assert len(res) == 1 and res[0]["ok"] and res[0]["approval"] == "queued"     # .obsidian and Archive/ are skipped
    drain(svc)
    doc = client.get(f"/v1/knowledge/documents/{res[0]['item_id']}", headers=admin).json()
    assert doc["published"] and doc["item"]["category"] == "Scripts" and doc["item"]["provenance"] == "Sales playbook 2026"
    # the same note imported again is not written twice (§12 duplicate events)
    again = client.post("/v1/admin/documents/import-obsidian", headers=admin, files={"files": ("vault.zip", buf.getvalue(), "application/zip")}).json()
    assert again["results"][0].get("duplicate") is True


def test_browse_scope_and_sensitivity(stack):
    svc, client, sales, hr, ka = _setup(stack)
    admin, rev = login(client, "k_admin"), login(client, "k_rev")
    publish_doc(svc, client, admin, "Leave guide", LEAVE, sales)
    publish_doc(svc, client, admin, "Board notes", "# Board\nExpansion plans for 2027.", hr, sensitivity="confidential")
    finance = svc.users.department_by_name("Finance")["id"]
    publish_doc(svc, client, admin, "Invoice rules", "# Invoices\nInvoices go out on Fridays.", finance)
    titles = {d["title"] for d in client.get("/v1/knowledge/documents", headers=rev).json()["documents"]}
    assert titles == {"Leave guide"}                     # reviewer: own departments, and not the confidential HR note
    all_titles = {d["title"] for d in client.get("/v1/knowledge/documents", headers=admin).json()["documents"]}
    assert {"Leave guide", "Board notes", "Invoice rules"} <= all_titles
    board = next(d for d in client.get("/v1/knowledge/documents", headers=admin).json()["documents"] if d["title"] == "Board notes")
    assert client.get(f"/v1/knowledge/documents/{board['item_id']}", headers=rev).status_code == 404     # no metadata leak (AT-05)
    # a Sales proposal close to the confidential HR note: the reviewer is not told the note exists (AT-05), the admin is
    near = _propose_text(client, admin, "Board summary", "# Board\nExpansion plans for 2027 and the board.", sales)
    drain(svc)
    rel = lambda h: [r["title"] for r in client.get(f"/v1/knowledge/proposals/{near['proposal_id']}", headers=h).json()["related"]]
    assert "Board notes" not in rel(rev) and "Board notes" in rel(admin)
