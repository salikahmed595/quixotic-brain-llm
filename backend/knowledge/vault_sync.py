"""Obsidian sync: notes contributors push become reviewed proposals — PRD §8, §9, §1, §15; owner request 2026-10-20 (three
contributors, docs/PRD_GAPS.md §0).

Each contributor has a private repository (contributors.py): `main` holds only the published notes they may see, and they may push
only `proposals/<name>`. After each push the server hook calls POST /v1/integrations/vault/push; every note changed on the branch
since it split from their `main` becomes a proposal (create, update or archive) for the normal review. The SSH key is the verified
identity (§9 step 1); nothing is published without an approval (§1, §15). If the hook cannot reach the app, `reconcile` (run by the
worker) picks the push up later; a push is processed once (branch + commit)."""
from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from ..analytics import audit
from .contributors import ContributorRepos, visible_paths
from .service import Draft, KnowledgeError, KnowledgeService
from .vault import GitVault, VaultError, parse_note

log = logging.getLogger("vault_sync")


def queue_view_refresh(svc, actor=None, name: Optional[str] = None, empty: bool = False) -> None:
    """Ask the worker to rewrite contributor views (after a link, unlink or a change to someone's access). No-op when off."""
    if not getattr(svc.settings, "vault_contributors_dir", None) or not getattr(svc, "integrations", None):
        return
    if name is None and not svc.integrations.identities("obsidian"):
        return
    job = svc.ops.create_job("vault.refresh_views", {"name": name, "empty": empty}, actor)
    svc.queue.send(job, "vault.refresh_views")


def queue_refresh_for_user(svc, user_id, actor=None) -> None:
    if getattr(svc.settings, "vault_contributors_dir", None) and getattr(svc, "integrations", None):
        for name in svc.integrations.external_ids_for(user_id, "obsidian"):
            queue_view_refresh(svc, actor, name)


class VaultSync:
    def __init__(self, svc) -> None:
        self.svc = svc
        self.vault = GitVault(svc.settings.vault_dir, remote=svc.settings.vault_remote)
        self.repos = ContributorRepos(svc.settings.vault_contributors_dir, self.vault)

    def sync_branch(self, branch: str, commit: str) -> dict:
        if not branch.startswith("proposals/"):
            return {"ignored": "only proposals/<name> branches are synced"}
        name = branch.split("/", 1)[1]
        user = self.svc.integrations.user_for("obsidian", name)
        if user is None:
            return {"ignored": f"branch {branch} is not linked to an active user (System → Integrations)"}
        try:
            self.repos.fetch(name)
        except VaultError as e:
            return {"ignored": str(e)}
        head = self.repos.head(name) or commit
        if not self.svc.integrations.record_event("obsidian", f"{branch}:{head}", "push", user["id"]):
            return {"duplicate": True}
        principal = self.svc.users.principal(user)
        ks = KnowledgeService(self.svc)
        by_name = {d["name"].lower(): d["id"] for d in self.svc.users.list_departments(include_archived=False)}
        results = []
        for status, path in self.repos.branch_changes(name):
            # Same note content is proposed once, whatever the commit (a rejected note left on the branch is not re-proposed on
            # every push; editing it proposes it again) — duplicate detection.
            content = self.repos.show(name, f"origin/{branch}", path) if status != "D" else "deleted"
            ref = f"{branch}:{hashlib.sha256((content or '').encode()).hexdigest()[:16]}:{path}"
            if self.svc.knowledge.proposal_by_ref("obsidian", ref):
                continue
            try:
                out = self._one(ks, principal, user, by_name, name, status, path, ref)
                results.append({"note": path, **out})
                if out.get("proposal"):
                    self.svc.integrations.record_event("obsidian", ref, "proposal", user["id"], UUID(str(out["proposal"])))
            except KnowledgeError as e:
                results.append({"note": path, "error": str(e)})
        audit.record(self.svc.ops, audit.KNOWLEDGE_SUBMISSION, user["id"], user["employee_id"], action="obsidian_push", branch=branch,
                     commit=head, notes=len(results))
        self._tell(user, results)
        return {"results": results}

    def _one(self, ks: KnowledgeService, principal, user, by_name, name, status, path, ref) -> dict:
        branch = f"proposals/{name}"
        main_text = self.repos.show(name, "main", path)
        main_fm, _ = parse_note(main_text) if main_text else ({}, "")
        visible = set(visible_paths(self.svc, principal))       # §10: a contributor changes only notes they may see
        if status == "D":
            item_id = main_fm.get("id")
            if item_id:
                gone = self.svc.knowledge.get_item(UUID(str(item_id)))
                if not gone or gone["vault_path"] not in visible:
                    raise KnowledgeError(403, "you can only remove notes that are in your view")
            if not item_id:
                return {"skipped": "deleted a note that was never published"}
            return {"proposal": ks.propose_archive(principal, UUID(str(item_id)), f"Deleted in Obsidian ({path})")["proposal_id"]}
        text = self.repos.show(name, f"origin/{branch}", path) or ""
        fm, body = parse_note(text)
        if not body.strip():
            raise KnowledgeError(422, "the note is empty")
        item_id = fm.get("id") or main_fm.get("id")
        try:
            item = self.svc.knowledge.get_item(UUID(str(item_id))) if item_id else None
        except ValueError:
            raise KnowledgeError(422, "the note's `id:` is not valid; remove it to propose a new note") from None
        if item_id and (item is None or item["vault_path"] not in visible):
            raise KnowledgeError(403, "you can only change notes that are in your view (remove `id:` to propose a new note)")
        names = fm.get("departments") or fm.get("department") or []
        names = [names] if isinstance(names, str) else names
        depts = [by_name[n.lower()] for n in names if isinstance(n, str) and n.lower() in by_name]
        if not depts and item:
            depts = list(item["department_ids"])
        if not depts:
            raise KnowledgeError(422, "add `departments:` to the note's front matter (e.g. departments: [Sales])")
        sensitivity = str(fm.get("sensitivity") or (item["sensitivity"] if item else "") or "")
        if not sensitivity:
            raise KnowledgeError(422, "add `sensitivity:` to the note's front matter")
        exp = fm.get("expires")
        d = Draft(title=str(fm.get("title") or (item["title"] if item else path.rsplit("/", 1)[-1].removesuffix(".md"))).strip(),
                  body=body.strip(), department_ids=depts, sensitivity=sensitivity, category=fm.get("category") or (item["category"] if item else None),
                  owner_id=item["owner_id"] if item else user["id"], provenance=str(fm.get("source") or f"Obsidian ({path})"),
                  effective_date=fm.get("effective_date") if isinstance(fm.get("effective_date"), date) else None,
                  expires_at=datetime.combine(exp, datetime.min.time()) if isinstance(exp, date) else None,
                  change_note=str(fm.get("change") or f"Edited in Obsidian ({path})"))
        out = ks.propose_update(principal, item["id"], d, source="obsidian", source_ref=ref) if item else \
            ks.propose_new(principal, d, source="obsidian", source_ref=ref)
        return {"proposal": out["proposal_id"], "kind": "update" if item else "create"}

    def _tell(self, user: dict, results: list[dict]) -> None:
        ok = [r for r in results if r.get("proposal")]
        bad = [r for r in results if r.get("error")]
        if not ok and not bad:
            return
        lines = [f"{len(ok)} note(s) sent for review."] + [f"Not sent: {r['note']} — {r['error']}" for r in bad]
        lines.append(f"{self.svc.settings.public_url}/#/approvals")
        text = "\n".join(lines)
        bot = getattr(self.svc, "approvals_bot", None)
        if bot:
            bot.notify_user(user, "Obsidian sync", text)
        if getattr(self.svc, "mailer", None):
            from ..notifications.mail import send_safely
            send_safely(self.svc.mailer, user["email"], "Your Obsidian notes were received", text)

    def refresh_views(self, only: Optional[str] = None) -> dict:
        """Write each contributor's `main` = the published notes they may see now (after a publication, a link, or a change to
        their account), then merge it into their branch. Inactive accounts get an empty view (§5 FR-AUTH-03)."""
        out = {}
        for ident in self.svc.integrations.identities("obsidian"):
            name = ident["external_id"]
            if only and name != only:
                continue
            try:
                user = self.svc.users.get(ident["user_id"])
                active = user and user["account_status"] == "active"
                paths = visible_paths(self.svc, self.svc.users.principal(user)) if active else None
                res = self.repos.refresh(name, paths)
                out[name] = res
                if res["changed"]:
                    self.svc.integrations.record_event("obsidian", f"view:{name}:{self.repos._git('rev-parse', 'main', cwd=self.repos.view(name))}",
                                                       "view_refresh", ident["user_id"])
                if res["conflict"]:
                    self.svc.integrations.record_event("obsidian", f"conflict:{name}:{self.repos.head(name)}", "conflict", ident["user_id"])
            except Exception as e:
                log.exception("could not refresh the view of %s", name)
                out[name] = {"error": str(e)}
        return out

    refresh_branches = refresh_views                     # called after every publication (service._after_publish)

    def reconcile(self) -> dict:
        """Failure recovery: pushes whose hook could not reach the app (or arrived while it was down) are processed now."""
        out = {}
        for ident in self.svc.integrations.identities("obsidian"):
            name = ident["external_id"]
            try:
                self.repos.fetch(name)
                head = self.repos.head(name)
                if head:
                    out[name] = self.sync_branch(f"proposals/{name}", head)
            except Exception as e:
                log.exception("could not reconcile %s", name)
                out[name] = {"error": str(e)}
        return out
