"""Obsidian sync: notes the CEO pushes become reviewed proposals — docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md H4, PRD §8, §9, §1.

The CEO works in the normal Obsidian app with the Obsidian Git plugin. Their vault pushes to the server's bare repository, but the
server hook accepts only their own `proposals/<name>` branch; `main` (the published vault) is written by this backend alone.
After each push the hook calls POST /v1/integrations/vault/push; every note changed on the branch since it split from `main`
becomes a proposal (create, update or archive) for the normal review. The SSH key is the verified identity (§9 step 1), so these
proposals go straight to review; nothing is published without an approval (§1, §15)."""
from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from uuid import UUID

from ..analytics import audit
from .service import Draft, KnowledgeError, KnowledgeService
from .vault import GitVault, parse_note

log = logging.getLogger("vault_sync")


class VaultSync:
    def __init__(self, svc) -> None:
        self.svc = svc
        self.vault = GitVault(svc.settings.vault_dir, remote=svc.settings.vault_remote)

    def sync_branch(self, branch: str, commit: str) -> dict:
        if not branch.startswith("proposals/"):
            return {"ignored": "only proposals/<name> branches are synced"}
        name = branch.split("/", 1)[1]
        user = self.svc.integrations.user_for("obsidian", name)
        if user is None:
            return {"ignored": f"branch {branch} is not linked to an active user (System → Integrations)"}
        if not self.svc.integrations.record_event("obsidian", f"{branch}:{commit}", "push", user["id"]):
            return {"duplicate": True}
        principal = self.svc.users.principal(user)
        ks = KnowledgeService(self.svc)
        by_name = {d["name"].lower(): d["id"] for d in self.svc.users.list_departments(include_archived=False)}
        self.vault.fetch()
        results = []
        for status, path in self.vault.branch_changes(branch):
            # Same note content is proposed once, whatever the commit (a rejected note left on the branch is not re-proposed on
            # every push; editing it proposes it again).
            content = self.vault.show(f"origin/{branch}", path) if status != "D" else "deleted"
            ref = f"{branch}:{hashlib.sha256((content or '').encode()).hexdigest()[:16]}:{path}"
            if self.svc.knowledge.proposal_by_ref("obsidian", ref):
                continue
            try:
                results.append({"note": path, **self._one(ks, principal, user, by_name, branch, status, path, ref)})
            except KnowledgeError as e:
                results.append({"note": path, "error": str(e)})
        audit.record(self.svc.ops, audit.KNOWLEDGE_SUBMISSION, user["id"], user["employee_id"], action="obsidian_push", branch=branch,
                     notes=len(results))
        self._tell(user, results)
        return {"results": results}

    def _one(self, ks: KnowledgeService, principal, user, by_name, branch, status, path, ref) -> dict:
        main_text = self.vault.show("main", path)
        main_fm, _ = parse_note(main_text) if main_text else ({}, "")
        if status == "D":
            item_id = main_fm.get("id")
            if not item_id:
                return {"skipped": "deleted a note that was never published"}
            return {"proposal": ks.propose_archive(principal, UUID(str(item_id)), f"Deleted in Obsidian ({path})")["proposal_id"]}
        text = self.vault.show(f"origin/{branch}", path) or ""
        fm, body = parse_note(text)
        if not body.strip():
            raise KnowledgeError(422, "the note is empty")
        item_id = fm.get("id") or main_fm.get("id")
        item = self.svc.knowledge.get_item(UUID(str(item_id))) if item_id else None
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

    def refresh_branches(self) -> None:
        """After a publication, every linked person's branch receives the official notes."""
        for ident in self.svc.integrations.identities("obsidian"):
            try:
                self.vault.merge_main_into(f"proposals/{ident['external_id']}")
            except Exception:
                log.exception("could not refresh branch proposals/%s", ident["external_id"])
