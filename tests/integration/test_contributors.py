"""Three Obsidian contributors, each with a private repository (owner request 2026-10-20; backend/knowledge/contributors.py).
End to end on a real PostgreSQL and real Git: filtered views (§10), push -> proposal -> review (approve / request changes) ->
controlled publication -> RAG (§8, §9), duplicates, conflicts, restricted notes, suspension, missed pushes, SSH key wrapper."""
import json
import os
import subprocess
import time
from pathlib import Path
from uuid import UUID

import pytest

from backend.api.v1.integrations import sign
from backend.auth.security import hash_password
from backend.database.integrations import IntegrationStore
from backend.knowledge.vault_sync import VaultSync
from backend.permissions.roles import Role
from tests.integration.test_e2e import drain, login, publish_doc, second_approver, stack  # noqa: F401  (fixture)

SECRET = "vault-hook-secret-vault-hook-secret-1234"


def _signed(client, path, body: dict, secret=SECRET, ts=None):
    """A call as the Obsidian Git hook makes it: HMAC-SHA256(QB_VAULT_HOOK_SECRET, "<timestamp>.<body>")."""
    raw = json.dumps(body).encode()
    ts = str(int(ts if ts is not None else time.time()))
    return client.post(path, content=raw, headers={"Content-Type": "application/json", "X-Quixotic-Timestamp": ts,
                                                   "X-Quixotic-Signature": sign(secret, ts, raw)})

ROOT = Path(__file__).resolve().parents[2]


def _git(*args, cwd, env=None):
    e = {**os.environ, **(env or {})}
    e.pop("QUIXOTIC_BACKEND", None)
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=e)
    if r.returncode:
        raise AssertionError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout.strip()


def _try_push(cwd, *args):
    e = {**os.environ}
    e.pop("QUIXOTIC_BACKEND", None)
    return subprocess.run(["git", "push", "origin", *args], cwd=cwd, capture_output=True, text=True, env=e)


NOTE = "---\ndepartments: [{dept}]\nsensitivity: internal\n---\n\n# {title}\n{body}\n"


@pytest.fixture()
def world(stack, tmp_path):
    svc, client = stack
    svc.settings = svc.settings.model_copy(update={"vault_hook_secret": SECRET, "vault_contributors_dir": str(tmp_path / "contrib")})
    svc.integrations = IntegrationStore(svc.pool, svc.settings.tenant_id)
    d = lambda n: svc.users.department_by_name(n)["id"]
    sales, hr = d("Sales"), d("HR")
    admin = svc.users.create_user("c_admin", "c_admin@q.ai", "Adam Admin", hash_password("pw12345"), Role.SYSTEM_ADMIN, [])
    ceo = svc.users.create_user("c_ceo", "c_ceo@q.ai", "Cara CEO", hash_password("pw12345"), Role.FOUNDER_CEO, [])
    lead = svc.users.create_user("c_lead", "c_lead@q.ai", "Sam Lead", hash_password("pw12345"), Role.DEPARTMENT_REVIEWER, [sales])
    hrp = svc.users.create_user("c_hr", "c_hr@q.ai", "Hana HR", hash_password("pw12345"), Role.EMPLOYEE, [hr])
    svc.users.create_user("c_seller", "c_seller@q.ai", "Sid Seller", hash_password("pw12345"), Role.EMPLOYEE, [sales])
    h = login(client, "c_admin")
    publish_doc(svc, client, h, "Upsell script", "# Upsell script\n## Offer\nOffer the matching frame after the first artwork.", sales)
    publish_doc(svc, client, h, "Leave rules", "# Leave rules\n## Requests\nRequest leave 24 hours before the shift.", hr)
    publish_doc(svc, client, h, "Commission bands", "# Commission bands\n## Bands\nBand C earns the quarterly kicker.", sales,
                sensitivity="confidential")
    for name, uid in (("ceo", ceo), ("sales", lead), ("hr", hrp)):
        assert client.post("/v1/admin/integrations/identities", headers=h,
                           json={"platform": "obsidian", "external_id": name, "user_id": str(uid)}).status_code == 201
    drain(svc)                                               # the link queued "vault.refresh_views": repositories are created
    laptops = {}
    for name in ("ceo", "sales", "hr"):
        lap = tmp_path / f"laptop-{name}"
        _git("clone", "-q", str(tmp_path / "contrib" / f"{name}.git"), str(lap), cwd=tmp_path)
        _git("config", "user.email", f"{name}@q.ai", cwd=lap); _git("config", "user.name", name, cwd=lap)
        _git("checkout", "-q", "-b", f"proposals/{name}", cwd=lap)
        laptops[name] = lap
    return svc, client, h, laptops, {"sales": sales, "hr": hr, "hr_user": hrp}


def _files(lap):
    return sorted(p.relative_to(lap).as_posix() for p in lap.rglob("*.md") if ".git" not in p.parts and p.name != "README.md")


def _push(client, lap, name, msg="notes"):
    _git("add", "-A", cwd=lap); _git("commit", "-q", "-m", msg, cwd=lap)
    r = _try_push(lap, f"proposals/{name}")
    assert r.returncode == 0, r.stderr
    res = _signed(client, "/v1/integrations/vault/push", {"branch": f"proposals/{name}", "commit": _git("rev-parse", "HEAD", cwd=lap)})
    assert res.status_code == 202, res.text
    return res.json()


def test_each_contributor_sees_only_permitted_published_notes(world):
    svc, client, h, laps, ids = world
    titles = lambda name: {Path(f).stem.split("--")[0].replace("-", " ") for f in _files(laps[name])}
    assert titles("ceo") == {"Upsell script", "Leave rules", "Commission bands"}      # Founder/CEO: everything
    assert titles("sales") == {"Upsell script"}                                       # Sales, internal only: no HR, no confidential
    assert titles("hr") == {"Leave rules"}
    # a contributor cannot read another contributor's repository or the backend's vault through their own clone
    assert "proposals/ceo" not in _git("ls-remote", "origin", cwd=laps["hr"])


def test_three_contributor_workflows_from_push_to_answer(world):
    svc, client, h, laps, ids = world
    seller = login(client, "c_seller")
    search = lambda q: " ".join(r["source"] + " " + r["text"] for r in client.post("/v1/search", headers=seller, json={"question": q}).json()["results"])

    # 1) CEO: a new Sales note
    (laps["ceo"] / "Sales").mkdir(exist_ok=True)
    (laps["ceo"] / "Sales" / "Gold frame offer.md").write_text(NOTE.format(dept="Sales", title="Gold frame offer",
                                                               body="Offer the gold frame bundle to returning clients."), encoding="utf-8")
    ceo_res = _push(client, laps["ceo"], "ceo")["results"]
    p_ceo = ceo_res[0]["proposal"]
    # 2) Sales lead: edits the published Upsell script (an update proposal for the same document)
    f = next(laps["sales"].rglob("Upsell-script--*.md"))
    f.write_text(f.read_text(encoding="utf-8").replace("matching frame", "matching walnut frame"), encoding="utf-8")
    sales_res = _push(client, laps["sales"], "sales")["results"]
    assert sales_res[0]["kind"] == "update"
    p_sales = sales_res[0]["proposal"]
    # 3) HR: a new HR note
    (laps["hr"] / "HR").mkdir(exist_ok=True)
    (laps["hr"] / "HR" / "Night allowance.md").write_text(NOTE.format(dept="HR", title="Night allowance",
                                                          body="Night shift staff receive the night allowance monthly."), encoding="utf-8")
    p_hr = _push(client, laps["hr"], "hr")["results"][0]["proposal"]
    drain(svc)

    # pending proposals never reach employee search (§8, §15)
    assert all(svc.knowledge.get_proposal(UUID(p))["status"] == "open" for p in (p_ceo, p_sales, p_hr))
    assert "Gold frame offer" not in search("gold frame bundle returning clients")
    # the same push again is not processed twice
    assert _signed(client, "/v1/integrations/vault/push",
                   {"branch": "proposals/ceo", "commit": _git("rev-parse", "HEAD", cwd=laps["ceo"])}).json() == {"duplicate": True}

    # review: request corrections on HR's note; HR fixes it and pushes again -> a new proposal
    r = client.post(f"/v1/admin/proposals/{p_hr}/request-changes", headers=h, json={"note": "Say which month it is paid."})
    assert r.status_code == 200 and svc.knowledge.get_proposal(UUID(p_hr))["status"] == "changes_requested"
    note = laps["hr"] / "HR" / "Night allowance.md"
    note.write_text(note.read_text(encoding="utf-8").replace("monthly.", "with the next month's salary."), encoding="utf-8")
    p_hr2 = _push(client, laps["hr"], "hr", "fix")["results"][0]["proposal"]
    assert p_hr2 != p_hr
    drain(svc)
    for p in (p_ceo, p_sales, p_hr2):
        a = client.post(f"/v1/admin/proposals/{p}/approve", headers=h, json={})
        if a.json().get("status") == "open":                 # a high-impact topic (e.g. pay) needs a second person (§9 step 5)
            a = client.post(f"/v1/admin/proposals/{p}/approve", headers=second_approver(svc, client), json={})
        assert a.status_code == 200 and a.json()["status"] == "approved", a.text
    drain(svc)                                        # publish -> index -> atomic switch -> views refreshed
    assert all(svc.knowledge.get_proposal(UUID(p))["status"] == "published" for p in (p_ceo, p_sales, p_hr2))

    # approved knowledge is searchable, the old wording is gone (re-indexed)
    assert "Gold frame offer" in search("gold frame bundle returning clients")
    hits = client.post("/v1/search", headers=seller, json={"question": "walnut frame first artwork"}).json()["results"]
    assert any("walnut" in r["text"] for r in hits) and not any("matching frame" in r["text"] for r in hits)
    # each view follows the permissions: the Sales lead now has the CEO's Sales note, HR does not
    _git("pull", "-q", "origin", "proposals/sales", cwd=laps["sales"]); _git("pull", "-q", "origin", "proposals/hr", cwd=laps["hr"])
    assert any(p.endswith("Gold frame offer.md") for p in _files(laps["sales"]))
    assert not any("Gold frame" in p or "Commission" in p for p in _files(laps["hr"]))

    # activity log per contributor
    ev = client.get("/v1/admin/integrations/obsidian/activity", headers=h).json()["events"]
    assert {e["contributor"] for e in ev if e["kind"] == "push"} == {"ceo", "sales", "hr"}
    assert any(e["kind"] == "proposal" and e["proposal_status"] == "changes_requested" for e in ev)


def test_restricted_notes_conflicts_deletes_suspension_and_missed_pushes(world):
    svc, client, h, laps, ids = world
    # HR copies the id of a confidential Sales note it cannot see: refused
    item = next(i for i in svc.knowledge.published_vault_files() if i["sensitivity"] == "confidential")
    (laps["hr"] / "steal.md").write_text(f"---\nid: {item['id']}\ndepartments: [HR]\nsensitivity: internal\n---\n\n# x\nnew text\n",
                                        encoding="utf-8")
    res = _push(client, laps["hr"], "hr")["results"]
    assert "your view" in res[0]["error"]
    # HR may only push its own branch; no force-push
    assert _try_push(laps["hr"], "HEAD:refs/heads/main").returncode != 0
    assert _try_push(laps["hr"], "HEAD:refs/heads/proposals/ceo").returncode != 0

    # two people change the same note: the second waits for the first decision
    for name in ("ceo", "sales"):
        f = next(laps[name].rglob("Upsell-script--*.md"))
        f.write_text(f.read_text(encoding="utf-8") + f"\nExtra line from {name}.\n", encoding="utf-8")
    first = _push(client, laps["ceo"], "ceo")["results"][0]
    second = _push(client, laps["sales"], "sales")["results"][0]
    assert first.get("proposal") and "already has a change waiting" in second["error"]

    # deleting a published note proposes archiving it (reviewed like everything else)
    svc.knowledge  # noqa
    (next(laps["ceo"].rglob("Leave-rules--*.md"))).unlink()
    res = _push(client, laps["ceo"], "ceo", "remove")["results"]
    arch = next(r for r in res if "Leave-rules--" in r["note"])
    assert svc.knowledge.get_proposal(UUID(arch["proposal"]))["kind"] == "archive"

    # a push the hook could not deliver is picked up by the worker's reconcile
    (laps["sales"] / "Sales").mkdir(exist_ok=True)
    (laps["sales"] / "Sales" / "Late note.md").write_text(NOTE.format(dept="Sales", title="Late note", body="Arrived while offline."),
                                                          encoding="utf-8")
    _git("add", "-A", cwd=laps["sales"]); _git("commit", "-q", "-m", "late", cwd=laps["sales"])
    assert _try_push(laps["sales"], "proposals/sales").returncode == 0
    out = VaultSync(svc).reconcile()
    assert any(r["note"].endswith("Late note.md") and r.get("proposal") for r in out["sales"]["results"])

    # suspension: the view is emptied and pushes are ignored (§5 FR-AUTH-03)
    assert client.post(f"/v1/admin/users/{ids['hr_user']}/status", headers=h, json={"status": "suspended", "note": "test"}).status_code == 200
    drain(svc)
    _git("fetch", "-q", "origin", cwd=laps["hr"])
    assert [f for f in _git("ls-tree", "-r", "--name-only", "origin/main", cwd=laps["hr"]).splitlines() if f != "README.md"] == []
    r = _signed(client, "/v1/integrations/vault/push", {"branch": "proposals/hr", "commit": "0" * 40}).json()
    assert "not linked to an active user" in r.get("ignored", ""), r


def test_ssh_key_wrapper_allows_only_own_repository(tmp_path):
    fake = tmp_path / "bin"; fake.mkdir()
    (fake / "git-shell").write_text('#!/bin/sh\necho "RUN $2"\n', encoding="utf-8", newline="\n")
    (fake / "git-shell").chmod(0o755)
    shell = (ROOT / "deploy" / "vault" / "vault-shell").as_posix()

    def run(name, cmd):
        env = {**os.environ, "PATH": f"{fake.as_posix()}{os.pathsep}{os.environ['PATH']}", "SSH_ORIGINAL_COMMAND": cmd,
               "QUIXOTIC_CONTRIBUTORS_DIR": "/srv/vault/contributors"}
        return subprocess.run(["sh", shell, name], capture_output=True, text=True, env=env)
    ok = run("ceo", "git-upload-pack 'contributors/ceo.git'")
    assert ok.returncode == 0 and "RUN git-upload-pack '/srv/vault/contributors/ceo.git'" in ok.stdout
    assert run("ceo", "git-receive-pack '/srv/vault/contributors/ceo.git'").returncode == 0
    for bad in ("git-upload-pack 'contributors/hr.git'", "git-upload-pack '/srv/vault/work'", "git-upload-pack '../work'",
                "bash -i", "git-upload-pack 'contributors/ceo.git'; rm -rf /", "scp -f x"):
        assert run("ceo", bad).returncode != 0, bad
    assert run("Bad Name", "git-upload-pack 'x'").returncode != 0


def test_admin_links_accounts_and_endpoints_are_off_without_configuration(stack, tmp_path):
    """PRD §9 step 1 (identity mapping, admin only) and deny by default (§3): Obsidian is the only platform; without
    QB_VAULT_HOOK_SECRET the push endpoint does not exist."""
    svc, client = stack
    svc.integrations = IntegrationStore(svc.pool, svc.settings.tenant_id)
    svc.users.create_user("i_admin", "i_admin@q.ai", "Ivy", hash_password("pw12345"), Role.SYSTEM_ADMIN, [])
    uid = svc.users.create_user("i_emp", "i_emp@q.ai", "Ed", hash_password("pw12345"), Role.EMPLOYEE, [])
    h = login(client, "i_admin")
    link = lambda **kw: client.post("/v1/admin/integrations/identities", headers=h, json={"user_id": str(uid), **kw})  # noqa: E731
    assert link(platform="discord", external_id="ed").status_code == 422          # Obsidian only
    assert link(platform="obsidian", external_id="not a branch!").status_code == 422
    assert link(platform="obsidian", external_id="ed-notes").status_code == 201
    assert link(external_id="ed-notes").status_code == 409                          # platform defaults to obsidian
    listed = client.get("/v1/admin/integrations/identities", headers=h).json()
    assert [i["external_id"] for i in listed["identities"]] == ["ed-notes"] and set(listed) == {"identities", "obsidian"}
    assert listed["obsidian"] is False
    assert client.get("/v1/admin/integrations/identities", headers=login(client, "i_emp")).status_code == 403
    assert _signed(client, "/v1/integrations/vault/push", {"branch": "proposals/ed-notes", "commit": "0" * 40}).status_code == 404
