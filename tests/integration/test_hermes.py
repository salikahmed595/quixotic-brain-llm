"""Hermes + Telegram + Obsidian on a real PostgreSQL and real Git repositories — PRD §9, §11, §13 AT-07
(verified leadership message -> proposal -> never in answers before approval -> approval publishes and reindexes -> bot confirms
version and link). Telegram itself is replaced by a recording fake; everything else is real."""
import json
import subprocess
import time
from uuid import UUID

import pytest

from backend.api.v1.integrations import sign
from backend.auth.security import hash_password
from backend.integrations.approvals_bot import ApprovalsBot
from backend.database.integrations import IntegrationStore
from backend.knowledge.vault_sync import VaultSync
from backend.permissions.roles import Role
from tests.integration.test_e2e import drain, login, second_approver, stack  # noqa: F401  (fixture)

SECRET = "hermes-shared-secret-hermes-shared-secret"
CEO_TG, ADMIN_TG, STRANGER_TG = "111", "222", "999"


class FakeTelegram:
    def __init__(self):
        self.sent, self.cleared, self.answers, self._n = [], [], [], 0

    def send(self, chat_id, text, buttons=None):
        self._n += 1
        self.sent.append({"chat": str(chat_id), "text": text, "buttons": buttons, "id": self._n})
        return self._n

    def clear_buttons(self, chat_id, message_id):
        self.cleared.append((str(chat_id), message_id))

    def answer_callback(self, cid, text):
        self.answers.append(text)

    def last(self, chat, contains=""):
        return [m for m in self.sent if m["chat"] == chat and contains in m["text"]][-1]


def _setup(stack, tmp_path, remote=None):
    svc, client = stack
    svc.settings = svc.settings.model_copy(update={"hermes_shared_secret": SECRET, "telegram_webhook_secret": SECRET,
                                                   "vault_remote": remote})
    svc.integrations = IntegrationStore(svc.pool, svc.settings.tenant_id)
    tg = FakeTelegram()
    svc.approvals_bot = ApprovalsBot(svc, tg)
    sales = svc.users.department_by_name("Sales")["id"]
    ceo = svc.users.create_user("h_ceo", "h_ceo@q.ai", "Cara CEO", hash_password("pw12345"), Role.FOUNDER_CEO, [])
    admin = svc.users.create_user("h_admin", "h_admin@q.ai", "Adam Admin", hash_password("pw12345"), Role.SYSTEM_ADMIN, [])
    svc.users.create_user("h_emp", "h_emp@q.ai", "Eve", hash_password("pw12345"), Role.EMPLOYEE, [sales])
    svc.integrations.add_identity("telegram", CEO_TG, ceo, "CEO phone", admin)
    svc.integrations.add_identity("telegram", ADMIN_TG, admin, None, admin)
    return svc, client, tg, sales, ceo, admin


def _signed(client, path, body: dict, secret=SECRET, ts=None):
    raw = json.dumps(body).encode()
    ts = str(int(ts if ts is not None else time.time()))
    return client.post(path, content=raw, headers={"Content-Type": "application/json", "X-Quixotic-Timestamp": ts,
                                                   "X-Quixotic-Signature": sign(secret, ts, raw)})


def _tap(client, who, data, update_id):
    return client.post("/v1/integrations/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
                       json={"update_id": update_id, "callback_query": {"id": f"cb{update_id}", "from": {"id": int(who)}, "data": data}})


def test_at07_leadership_message_to_published_answer(stack, tmp_path):
    svc, client, tg, sales, ceo, admin = _setup(stack, tmp_path)
    emp = login(client, "h_emp")
    ask = lambda: " ".join(r["text"] for r in client.post("/v1/search", headers=emp, json={"question": "upsell handoff bonus rule"}).json()["results"])
    body = {"telegram_user_id": CEO_TG, "message_id": "m1", "intent": "add_fact", "title": "Upsell handoff bonus",
            "body": "# Upsell handoff\nThe upseller takes over a client within one day after the first artwork is delivered.",
            "departments": ["Sales"], "sensitivity": "internal", "transcript": "the upseller takes over within one day"}
    # signed service-to-service only (§11): no / wrong / stale signature is refused
    assert client.post("/v1/integrations/hermes/knowledge-proposals", json=body).status_code == 401
    assert _signed(client, "/v1/integrations/hermes/knowledge-proposals", body, secret="x" * 40).status_code == 401
    assert _signed(client, "/v1/integrations/hermes/knowledge-proposals", body, ts=time.time() - 3600).status_code == 401
    assert _signed(client, "/v1/integrations/hermes/knowledge-proposals", {**body, "telegram_user_id": STRANGER_TG}).status_code == 403
    r = _signed(client, "/v1/integrations/hermes/knowledge-proposals", body)
    assert r.status_code == 201 and r.json()["status"] == "awaiting_confirmation", r.text
    pid = r.json()["proposal_id"]
    assert _signed(client, "/v1/integrations/hermes/knowledge-proposals", body).json().get("duplicate")     # same message: once
    drain(svc)
    confirm = tg.last(CEO_TG, "Please confirm")
    assert "heard as" in confirm["text"] and confirm["buttons"][0][0] == ("Confirm", f"c:{pid}")
    assert not [m for m in tg.sent if m["chat"] == ADMIN_TG]                  # reviewers are not asked before confirmation
    # only the real sender can confirm (identity comes from Telegram, not from the model)
    _tap(client, ADMIN_TG, f"c:{pid}", 1)
    assert "Only the person who sent this" in tg.answers[-1]
    _tap(client, STRANGER_TG, f"c:{pid}", 2)
    assert "not linked" in tg.answers[-1]
    assert svc.knowledge.get_proposal(UUID(pid))["status"] == "awaiting_confirmation"
    _tap(client, CEO_TG, f"c:{pid}", 3)
    _tap(client, CEO_TG, f"c:{pid}", 3)                                       # duplicate delivery is ignored (§12)
    assert svc.knowledge.get_proposal(UUID(pid))["status"] == "open"
    review = tg.last(ADMIN_TG, "Review needed")
    assert review["buttons"][0] == [("Approve", f"a:{pid}"), ("Reject", f"r:{pid}")]
    assert "upseller" not in ask()                                            # unapproved change never appears in answers (AT-07)
    _tap(client, ADMIN_TG, f"a:{pid}", 4)                                     # admin approves in Telegram -> publishes
    assert tg.answers[-1].startswith("Approved")
    drain(svc)
    p = svc.knowledge.get_proposal(UUID(pid))
    assert p["status"] == "published" and any(d["via"] == "telegram" for d in svc.knowledge.decisions(UUID(pid)))
    assert "upseller takes over" in ask()                                     # reindexed and searchable
    done = tg.last(CEO_TG, "Published")
    assert "#/knowledge?doc=" in done["text"]                                 # bot confirms with a document link (§9 step 6)
    # the agent can follow up on it and search like the person could
    st = _signed(client, "/v1/integrations/hermes/proposal-status", {"telegram_user_id": CEO_TG, "proposal_id": pid}).json()
    assert st["status"] == "published" and st["approvals"] == 1
    found = _signed(client, "/v1/integrations/hermes/search", {"telegram_user_id": CEO_TG, "query": "upsell handoff"}).json()["results"]
    assert found and found[0]["title"] == "Upsell handoff bonus"


def test_high_impact_telegram_change_needs_two_people_and_cancel_works(stack, tmp_path):
    svc, client, tg, sales, ceo, admin = _setup(stack, tmp_path)
    body = {"telegram_user_id": CEO_TG, "message_id": "m9", "intent": "replace_policy", "title": "Refund window",
            "body": "# Refunds\nRefunds are possible within 30 days.", "departments": ["Sales"], "sensitivity": "internal"}
    pid = _signed(client, "/v1/integrations/hermes/knowledge-proposals", body).json()["proposal_id"]
    drain(svc)
    _tap(client, CEO_TG, f"c:{pid}", 10)
    _tap(client, CEO_TG, f"a:{pid}", 11)                                      # the CEO approves their own change ...
    assert "Still needs" in tg.answers[-1]                                    # ... a refund rule needs a second person (§9 step 5)
    _tap(client, ADMIN_TG, f"a:{pid}", 12)
    drain(svc)
    assert svc.knowledge.get_proposal(UUID(pid))["status"] == "published"
    other = _signed(client, "/v1/integrations/hermes/knowledge-proposals", {**body, "message_id": "m10", "title": "Draft idea",
                                                                            "body": "# Idea\nmaybe"}).json()["proposal_id"]
    _tap(client, CEO_TG, f"x:{other}", 13)
    assert svc.knowledge.get_proposal(UUID(other))["status"] == "withdrawn"
    assert _signed(client, "/v1/integrations/hermes/knowledge-proposals", {**body, "message_id": "m11", "departments": ["Nope"]}).status_code == 422


def _git(*args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_obsidian_branch_push_becomes_proposals_and_branch_gets_the_official_note(stack, tmp_path):
    bare = tmp_path / "vault.git"
    _git("init", "--bare", "-b", "main", str(bare), cwd=tmp_path)
    svc, client, tg, sales, ceo, admin = _setup(stack, tmp_path, remote=str(bare))
    svc.integrations.add_identity("obsidian", "ceo", ceo, "CEO laptop", admin)
    VaultSync(svc).vault.ensure()                                             # the backend creates main in the shared repo
    laptop = tmp_path / "laptop"
    _git("clone", str(bare), str(laptop), cwd=tmp_path)
    _git("config", "user.email", "ceo@q.ai", cwd=laptop); _git("config", "user.name", "CEO", cwd=laptop)
    _git("checkout", "-b", "proposals/ceo", cwd=laptop)
    (laptop / "Sales").mkdir()
    (laptop / "Sales" / "Upsell script.md").write_text("---\ndepartments: [Sales]\nsensitivity: internal\ncategory: Scripts\n---\n\n"
                                                       "# Upsell\nOffer the matching frame after the first artwork.\n", encoding="utf-8")
    (laptop / "Sales" / "No metadata.md").write_text("# Oops\nno front matter", encoding="utf-8")
    _git("add", ".", cwd=laptop); _git("commit", "-m", "notes", cwd=laptop); _git("push", "origin", "proposals/ceo", cwd=laptop)
    head = _git("rev-parse", "HEAD", cwd=laptop)
    r = _signed(client, "/v1/integrations/vault/push", {"branch": "proposals/ceo", "commit": head})
    assert r.status_code == 202, r.text
    res = {x["note"]: x for x in r.json()["results"]}
    assert res["Sales/Upsell script.md"].get("proposal") and "departments" in res["Sales/No metadata.md"]["error"]
    assert _signed(client, "/v1/integrations/vault/push", {"branch": "proposals/ceo", "commit": head}).json() == {"duplicate": True}
    pid = res["Sales/Upsell script.md"]["proposal"]
    drain(svc)
    assert login(client, "h_admin") and client.post(f"/v1/admin/proposals/{pid}/approve", headers=login(client, "h_admin"), json={}).json()["status"] == "approved"
    drain(svc)
    assert svc.knowledge.get_proposal(UUID(pid))["status"] == "published"
    # main (written only by the backend) has the official note at the CEO's path; the CEO's branch received it
    official = _git("show", "main:Sales/Upsell script.md", cwd=bare)
    assert official.startswith("---\nid:") and "approved_by: Adam Admin" in official
    _git("pull", "origin", "proposals/ceo", cwd=laptop)
    assert (laptop / "Sales" / "Upsell script.md").read_text(encoding="utf-8").startswith("---\nid:")
    # the CEO edits the published note: an update proposal for the same document
    note = (laptop / "Sales" / "Upsell script.md").read_text(encoding="utf-8").replace("matching frame", "matching gold frame")
    (laptop / "Sales" / "Upsell script.md").write_text(note, encoding="utf-8")
    _git("commit", "-am", "edit", cwd=laptop); _git("push", "origin", "proposals/ceo", cwd=laptop)
    r = _signed(client, "/v1/integrations/vault/push", {"branch": "proposals/ceo", "commit": _git("rev-parse", "HEAD", cwd=laptop)}).json()
    upd = next(x for x in r["results"] if x["note"] == "Sales/Upsell script.md")
    assert upd["kind"] == "update"
    assert svc.knowledge.get_proposal(UUID(upd["proposal"]))["item_id"] == svc.knowledge.get_proposal(UUID(pid))["item_id"]


def test_admin_links_accounts_and_endpoints_are_off_without_configuration(stack, tmp_path):
    svc, client = stack
    from backend.database.integrations import IntegrationStore as S
    svc.integrations = S(svc.pool, svc.settings.tenant_id)
    svc.users.create_user("i_admin", "i_admin@q.ai", "Ivy", hash_password("pw12345"), Role.SYSTEM_ADMIN, [])
    uid = svc.users.create_user("i_emp", "i_emp@q.ai", "Ed", hash_password("pw12345"), Role.EMPLOYEE, [])
    h = login(client, "i_admin")
    assert client.post("/v1/admin/integrations/identities", headers=h, json={"platform": "telegram", "external_id": "abc", "user_id": str(uid)}).status_code == 422
    assert client.post("/v1/admin/integrations/identities", headers=h, json={"platform": "telegram", "external_id": "4242", "user_id": str(uid)}).status_code == 201
    assert client.post("/v1/admin/integrations/identities", headers=h, json={"platform": "telegram", "external_id": "4242", "user_id": str(uid)}).status_code == 409
    listed = client.get("/v1/admin/integrations/identities", headers=h).json()
    assert listed["identities"][0]["external_id"] == "4242" and listed["hermes"] is False
    assert client.get("/v1/admin/integrations/identities", headers=login(client, "i_emp")).status_code == 403
    # not configured: the Hermes and Telegram endpoints do not exist
    assert _signed(client, "/v1/integrations/hermes/search", {"telegram_user_id": "4242", "query": "x"}).status_code == 404
    assert client.post("/v1/integrations/telegram/webhook", json={}).status_code == 404


def test_vault_server_hook_lets_people_push_only_their_proposals_branch(tmp_path):
    import os
    import shutil
    from pathlib import Path
    hook = Path(__file__).resolve().parents[2] / "deploy" / "vault" / "pre-receive"
    bare = tmp_path / "vault.git"
    _git("init", "--bare", "-b", "main", str(bare), cwd=tmp_path)
    shutil.copy(hook, bare / "hooks" / "pre-receive")
    os.chmod(bare / "hooks" / "pre-receive", 0o755)
    work = tmp_path / "w"
    _git("init", "-b", "main", str(work), cwd=tmp_path)
    _git("config", "user.email", "x@q.ai", cwd=work); _git("config", "user.name", "x", cwd=work)
    (work / "a.md").write_text("a", encoding="utf-8"); _git("add", ".", cwd=work); _git("commit", "-m", "a", cwd=work)
    _git("remote", "add", "origin", str(bare), cwd=work)

    def push(*args, **env):
        e = {**os.environ, **env}
        e.pop("QUIXOTIC_BACKEND", None) if "QUIXOTIC_BACKEND" not in env else None
        return subprocess.run(["git", "push", "origin", *args], cwd=work, capture_output=True, text=True, env=e)
    assert push("main", QUIXOTIC_BACKEND="1").returncode == 0                      # the backend writes main
    assert push("main:refs/heads/main2", QUIXOTIC_BRANCH="ceo").returncode != 0   # a person cannot
    assert push("main:refs/heads/proposals/other", QUIXOTIC_BRANCH="ceo").returncode != 0
    assert push("main:refs/heads/proposals/ceo", QUIXOTIC_BRANCH="ceo").returncode == 0
    _git("commit", "--amend", "-m", "rewritten", cwd=work)
    assert push("--force", "HEAD:refs/heads/proposals/ceo", QUIXOTIC_BRANCH="ceo").returncode != 0   # no force-push
    assert push(":refs/heads/proposals/ceo", QUIXOTIC_BRANCH="ceo").returncode != 0                  # no delete
