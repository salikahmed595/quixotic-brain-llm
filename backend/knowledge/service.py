"""Knowledge proposals, review and publication — PRD §1, §3, §7 (Add information, Documents, Approvals), §8, §9 steps 4–7.

Rules (PRD; choices where the PRD is silent are listed in docs/PRD_GAPS.md §0.7b):
- Every change to knowledge is a proposal reviewed by people; nothing is auto-approved (§1, §3, §15).
- Reviewers decide only for their own departments; Knowledge Admins with the publisher grant, System Admins and the Founder/CEO
  decide for every department (§3). Publication needs at least one decision by such a publisher.
- High-impact topics (HR, pay, discounts, refunds, customer payments, security — §9 step 5) need two different approvers.
- Publication is controlled (§8): index the new version, record it in the Git vault, switch the published version atomically,
  then check it can be retrieved; on any failure the previous version stays published and the owner is alerted (§9 step 7).
"""
from __future__ import annotations

import difflib
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from ..analytics import audit
from ..database.knowledge import APPROVED, ARCHIVED, DRAFT, PUBLISHED, UNDER_REVIEW
from ..permissions.access import Principal, resolve_department_scope
from ..permissions.roles import P, Role, can
from .vault import GitVault, VaultError, note_path, render_note

log = logging.getLogger("knowledge")

# PRD §9 step 5: "High-impact policies (HR, pay, discounts, refunds, customer payments, security) always require explicit
# confirmation and approval."
HIGH_IMPACT_TOPICS = ("hr", "pay", "payroll", "salary", "salaries", "discount", "discounts", "refund", "refunds",
                      "customer payment", "customer payments", "payment", "payments", "security")
_HIGH_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in HIGH_IMPACT_TOPICS) + r")\b", re.I)


class KnowledgeError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def checksum(text: Optional[str]) -> Optional[str]:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None


def is_high_impact(*texts: Optional[str]) -> bool:
    return any(t and _HIGH_RE.search(t) for t in texts)


def is_publisher(p: Principal) -> bool:
    return can(p.role, P.REVIEW_PROPOSALS) and (p.can_publish or p.role is Role.FOUNDER_CEO)


def may_review(p: Principal, department_ids) -> bool:
    """§3: publishers decide for every department; Department Reviewers only for the departments they review."""
    if not can(p.role, P.REVIEW_PROPOSALS):
        return False
    return is_publisher(p) or bool(set(department_ids) & set(p.managed_department_ids))


@dataclass
class Draft:
    title: str
    body: Optional[str]
    department_ids: list[UUID]
    sensitivity: str
    category: Optional[str] = None
    owner_id: Optional[UUID] = None
    provenance: Optional[str] = None
    effective_date: Optional[date] = None
    expires_at: Optional[datetime] = None
    change_note: Optional[str] = None
    high_impact: bool = False
    source_file_id: Optional[UUID] = None
    gap_id: Optional[UUID] = None                     # the knowledge gap this answers (§9 gap loop)

    def meta(self) -> dict:
        return {"title": self.title, "category": self.category, "department_ids": [str(d) for d in self.department_ids],
                "sensitivity": self.sensitivity, "owner_id": str(self.owner_id) if self.owner_id else None, "provenance": self.provenance}


class KnowledgeService:
    def __init__(self, svc) -> None:
        self.svc = svc
        self.store = svc.knowledge
        self.vault = GitVault(svc.settings.vault_dir)

    # ---- helpers ----
    def _enqueue(self, job_type: str, payload: dict, actor: Optional[UUID]) -> UUID:
        job_id = self.svc.ops.create_job(job_type, payload, actor)
        self.svc.queue.send(job_id, job_type)
        return job_id

    def _check_draft(self, actor: Principal, d: Draft) -> None:
        if not d.title.strip():
            raise KnowledgeError(422, "give the document a title")
        if not d.department_ids:
            raise KnowledgeError(422, "choose at least one department")
        allowed = resolve_department_scope(actor, self.svc.users.all_department_ids())
        if not set(d.department_ids) <= allowed:
            raise KnowledgeError(403, "you can only add knowledge for departments you may see")
        levels = self.svc.settings.sensitivity_levels
        if d.sensitivity not in levels:
            raise KnowledgeError(422, f"sensitivity must be one of {sorted(levels)}")
        if actor.role.value not in levels[d.sensitivity]:
            raise KnowledgeError(403, "you cannot propose a document at a sensitivity level you may not see yourself")
        if d.effective_date and d.expires_at and d.expires_at.date() <= d.effective_date:
            raise KnowledgeError(422, "the expiry date must be after the effective date")
        if d.owner_id is not None:
            owner = self.svc.users.get(d.owner_id)
            if not owner or owner["account_status"] != "active":
                raise KnowledgeError(422, "the document owner must be an active person")

    def _required(self, high: bool) -> int:
        return 2 if high else 1

    def _dept_names(self, ids) -> list[str]:
        names = {d["id"]: d["name"] for d in self.svc.users.list_departments()}
        return sorted(names.get(UUID(str(i)), str(i)) for i in ids)

    # ---- proposing (§7 Add information / Documents, §11 POST /knowledge/proposals) ----
    def propose_new(self, actor: Principal, d: Draft, *, source: str = "web", source_ref: Optional[str] = None) -> dict:
        self._check_draft(actor, d)
        if source_ref and (dup := self.store.proposal_by_ref(source, source_ref)):
            return {"proposal_id": str(dup["id"]), "duplicate": True}             # §12 bot events never write twice
        high = d.high_impact or is_high_impact(d.title, d.category, d.body, *self._dept_names(d.department_ids))
        item = self.store.create_document(d.title.strip(), d.category, d.department_ids, d.sensitivity, d.owner_id, d.provenance,
                                          actor.user_id)
        vid = self.store.create_version(item, d.body, d.source_file_id, actor.user_id, d.effective_date, d.expires_at, d.change_note,
                                        checksum=checksum(d.body), status=UNDER_REVIEW)
        pid = self.store.create_proposal(kind="create", item_id=item, version_id=vid, base_version_id=None, title=d.title.strip(),
                                         summary=d.change_note, meta=d.meta(), source=source, source_ref=source_ref,
                                         submitted_by=actor.user_id, high_impact=high, required_approvals=self._required(high),
                                         gap_id=d.gap_id)
        self._mark_gap_in_progress(d.gap_id)
        job = self._enqueue("knowledge.process", {"version_id": str(vid)}, actor.user_id)
        audit.record(self.svc.ops, audit.KNOWLEDGE_SUBMISSION, actor.user_id, actor.employee_id, proposal=pid, title=d.title,
                     kind="create", source=source, high_impact=high)
        self._notify_reviewers(pid)
        return {"proposal_id": str(pid), "item_id": str(item), "version_id": str(vid), "job_id": str(job), "high_impact": high}

    def propose_update(self, actor: Principal, item_id: UUID, d: Draft, *, source: str = "web",
                       source_ref: Optional[str] = None) -> dict:
        item = self.store.get_item(item_id)
        if item is None or not self._may_see(actor, item):
            raise KnowledgeError(404, "document not found")
        self._check_draft(actor, d)
        if source_ref and (dup := self.store.proposal_by_ref(source, source_ref)):
            return {"proposal_id": str(dup["id"]), "duplicate": True}
        if self.store.open_proposal_for(item_id):
            raise KnowledgeError(409, "this document already has a change waiting for review; decide that one first")
        base = self.store.published_version(item_id)
        body = d.body if d.body is not None or d.source_file_id else (base["body"] if base else None)
        high = d.high_impact or is_high_impact(d.title, d.category, body, item["category"], *item["departments"],
                                               *self._dept_names(d.department_ids))
        vid = self.store.create_version(item_id, body, d.source_file_id, actor.user_id, d.effective_date, d.expires_at, d.change_note,
                                        checksum=checksum(body), status=UNDER_REVIEW)
        pid = self.store.create_proposal(kind="update", item_id=item_id, version_id=vid, base_version_id=base["id"] if base else None,
                                         title=d.title.strip(), summary=d.change_note, meta=d.meta(), source=source,
                                         source_ref=source_ref, submitted_by=actor.user_id, high_impact=high,
                                         required_approvals=self._required(high), gap_id=d.gap_id)
        self._mark_gap_in_progress(d.gap_id)
        job = self._enqueue("knowledge.process", {"version_id": str(vid)}, actor.user_id)
        audit.record(self.svc.ops, audit.KNOWLEDGE_SUBMISSION, actor.user_id, actor.employee_id, proposal=pid, title=d.title,
                     kind="update", source=source, high_impact=high)
        self._notify_reviewers(pid)
        return {"proposal_id": str(pid), "item_id": str(item_id), "version_id": str(vid), "job_id": str(job), "high_impact": high}

    def propose_archive(self, actor: Principal, item_id: UUID, note: Optional[str]) -> dict:
        item = self.store.get_item(item_id)
        if item is None or not self._may_see(actor, item):
            raise KnowledgeError(404, "document not found")
        pub = self.store.published_version(item_id)
        if pub is None:
            raise KnowledgeError(409, "only a published document can be archived")
        if self.store.open_proposal_for(item_id):
            raise KnowledgeError(409, "this document already has a change waiting for review")
        high = is_high_impact(item["title"], item["category"], *item["departments"])
        pid = self.store.create_proposal(kind="archive", item_id=item_id, version_id=pub["id"], base_version_id=pub["id"],
                                         title=item["title"], summary=note, meta={}, source="web", source_ref=None,
                                         submitted_by=actor.user_id, high_impact=high, required_approvals=self._required(high))
        audit.record(self.svc.ops, audit.KNOWLEDGE_SUBMISSION, actor.user_id, actor.employee_id, proposal=pid, kind="archive",
                     title=item["title"])
        self._notify_reviewers(pid)
        return {"proposal_id": str(pid)}

    def propose_restore(self, actor: Principal, item_id: UUID, version_id: UUID, note: Optional[str]) -> dict:
        """§2 goal 6 / §8 rollback: publish an earlier version again (reviewed like any change)."""
        item = self.store.get_item(item_id)
        v = self.store.get_version(version_id)
        if item is None or v is None or v["item_id"] != item_id or not self._may_see(actor, item):
            raise KnowledgeError(404, "version not found")
        if v["status"] != ARCHIVED:
            raise KnowledgeError(409, "only an archived version can be restored")
        if self.store.open_proposal_for(item_id):
            raise KnowledgeError(409, "this document already has a change waiting for review")
        base = self.store.published_version(item_id)
        high = is_high_impact(item["title"], item["category"], v["body"], *item["departments"])
        pid = self.store.create_proposal(kind="restore", item_id=item_id, version_id=version_id, base_version_id=base["id"] if base else None,
                                         title=item["title"], summary=note, meta={}, source="web", source_ref=None,
                                         submitted_by=actor.user_id, high_impact=high, required_approvals=self._required(high))
        audit.record(self.svc.ops, audit.KNOWLEDGE_SUBMISSION, actor.user_id, actor.employee_id, proposal=pid, kind="restore",
                     title=item["title"], version=v["version"])
        self._notify_reviewers(pid)
        return {"proposal_id": str(pid)}

    def withdraw(self, actor: Principal, proposal_id: UUID) -> None:
        p = self.store.get_proposal(proposal_id)
        if p is None:
            raise KnowledgeError(404, "proposal not found")
        if p["submitted_by"] != actor.user_id and not can(actor.role, P.MANAGE_DOCUMENTS):
            raise KnowledgeError(403, "only the person who proposed it can withdraw it")
        if not self.store.set_proposal_status(proposal_id, "withdrawn", expect=("open", "changes_requested")):
            raise KnowledgeError(409, "this proposal can no longer be withdrawn")
        if p["kind"] in ("create", "update"):
            self.store.set_status(p["version_id"], DRAFT, actor.user_id, "proposal withdrawn")
        audit.record(self.svc.ops, audit.KNOWLEDGE_SUBMISSION, actor.user_id, actor.employee_id, proposal=proposal_id, action="withdrawn")

    def after_indexing(self, version_id: UUID) -> None:
        """Runs after a proposed version was parsed and indexed: an uploaded file's text can reveal a high-impact topic that the
        title did not (§9 step 5), so the requirement is raised (never lowered)."""
        v = self.store.get_version(version_id)
        for p in self.store.open_proposals_for_version(version_id):
            if not p["high_impact"] and is_high_impact(v["body"]):
                self.store.raise_to_high_impact(p["id"])
                audit.record(self.svc.ops, audit.ADMIN_ACTION, None, "system", action="high_impact_detected", proposal=p["id"])

    # ---- reviewing (§7 Approvals, §11 POST /admin/proposals/{id}/approve|reject) ----
    def proposal_departments(self, p: dict) -> list[UUID]:
        meta_depts = (p.get("meta") or {}).get("department_ids") or []
        item = self.store.get_item(p["item_id"])
        return list({UUID(str(x)) for x in meta_depts} | set(item["department_ids"] if item else []))

    def decide(self, actor: Principal, proposal_id: UUID, decision: str, note: Optional[str], via: str = "web") -> dict:
        p = self.store.get_proposal(proposal_id)
        if p is None:
            raise KnowledgeError(404, "proposal not found")
        depts = self.proposal_departments(p)
        if not may_review(actor, depts):
            raise KnowledgeError(403, "you cannot review changes for these departments")
        if p["status"] != "open":
            raise KnowledgeError(409, f"this proposal is {p['status'].replace('_', ' ')}")
        if decision != "approve" and not (note or "").strip():
            raise KnowledgeError(422, "say what should change (a short note for the person who proposed it)")
        if decision == "approve" and p["kind"] in ("create", "update") and p["version_status"] != UNDER_REVIEW:
            raise KnowledgeError(409, "this version is not waiting for review")
        if decision == "approve" and p["kind"] in ("create", "update") and p["indexed_checksum"] != p["checksum"]:
            raise KnowledgeError(409, "the document is still being read and indexed; try again in a moment")
        if not self.store.add_decision(proposal_id, actor.user_id, decision, (note or "").strip() or None, via):
            raise KnowledgeError(409, "you already recorded this decision")
        audit.record(self.svc.ops, audit.APPROVAL if decision == "approve" else audit.REJECTION, actor.user_id, actor.employee_id,
                     proposal=proposal_id, decision=decision, note=note, via=via, title=p["title"])
        if decision in ("reject", "request_changes"):
            status = "rejected" if decision == "reject" else "changes_requested"
            self.store.set_proposal_status(proposal_id, status, expect=("open",))
            if p["kind"] in ("create", "update"):
                self.store.set_status(p["version_id"], DRAFT, actor.user_id, f"{status.replace('_', ' ')}: {note}")
            self._notify_submitter(p, f"{'Rejected' if decision == 'reject' else 'Changes requested'}: {p['title']}",
                                   f"{note}\n\nReviewer: {self._name(actor.user_id)}")
            return {"status": status}
        return self._maybe_approve(proposal_id, actor)

    def _maybe_approve(self, proposal_id: UUID, actor: Principal) -> dict:
        p = self.store.get_proposal(proposal_id)
        approvals = [d for d in self.store.decisions(proposal_id) if d["decision"] == "approve"]
        approvers = {d["decided_by"] for d in approvals}
        has_publisher = any(d["can_publish"] or d["role"] == Role.FOUNDER_CEO.value for d in approvals)
        if len(approvers) < p["required_approvals"] or not has_publisher:
            missing = []
            if len(approvers) < p["required_approvals"]:
                missing.append(f"{p['required_approvals'] - len(approvers)} more approval(s) from a different person")
            if not has_publisher:
                missing.append("an approval by a publisher")
            return {"status": "open", "waiting_for": missing}
        if not self.store.set_proposal_status(proposal_id, "approved", expect=("open",)):
            raise KnowledgeError(409, "this proposal was decided meanwhile")
        if p["kind"] in ("create", "update"):
            self.store.set_status(p["version_id"], APPROVED, actor.user_id, "approved")
        job = self._enqueue("knowledge.publish", {"proposal_id": str(proposal_id), "approved_by": str(actor.user_id)}, actor.user_id)
        return {"status": "approved", "job_id": str(job)}

    # ---- publication (§8 controlled publication, §9 steps 6–7) — runs in the worker ----
    def publish(self, proposal_id: UUID, approved_by: Optional[UUID] = None) -> dict:
        p = self.store.get_proposal(proposal_id)
        if p is None or p["status"] not in ("approved", "failed"):
            raise KnowledgeError(409, "only approved proposals are published")
        self.store.set_proposal_status(proposal_id, "publishing")
        item = self.store.get_item(p["item_id"])
        actor = UUID(str(approved_by)) if approved_by else None
        previous, switched = None, False
        try:
            if p["kind"] == "archive":
                new_path, commit = self.vault.archive(item["vault_path"], f"Archive {item['title']} (approved by {self._name(actor)})")
                previous = self.store.switch_published(p["item_id"], None, actor, {}, new_path, commit, actor)
                switched = True
            else:
                v = self.store.get_version(p["version_id"])
                if v["indexed_checksum"] != v["checksum"] or not v["chunk_count"]:
                    self.svc.ingestion.process_version(v["id"])                   # (re)index before switching (§8)
                    v = self.store.get_version(p["version_id"])
                if not v["chunk_count"]:
                    raise KnowledgeError(422, "the new version has no readable text to index")
                meta = p.get("meta") or {}
                merged = {**item, **{k: val for k, val in meta.items() if val is not None}}
                dept_ids = meta.get("department_ids") or [str(x) for x in item["department_ids"]]
                dept_names = self._dept_names(dept_ids)
                path = note_path(str(item["id"]), merged["title"], dept_names)
                note = render_note({"id": str(item["id"]), "title": merged["title"], "category": merged.get("category"),
                                    "departments": dept_names, "sensitivity": merged.get("sensitivity"),
                                    "owner": self._name(merged.get("owner_id")), "approved_by": self._name(actor),
                                    "source": merged.get("provenance") or p["source"],
                                    "effective_date": v["effective_date"].isoformat() if v["effective_date"] else None,
                                    "expires": v["expires_at"].date().isoformat() if v["expires_at"] else None,
                                    "version": v["version"], "status": "published", "checksum": v["checksum"],
                                    "updated": datetime.now().date().isoformat()}, v["body"] or "")
                commit = self.vault.publish(path, item["vault_path"], note,
                                            f"Publish {merged['title']} v{v['version']} (approved by {self._name(actor)})")
                previous = self.store.switch_published(p["item_id"], v["id"], actor, meta, path, commit, actor)
                switched = True
                self._verify_retrievable(v["id"])
            self.store.set_proposal_status(proposal_id, "published")
            audit.record(self.svc.ops, audit.ADMIN_ACTION, actor, self._name(actor), action="knowledge_published", proposal=proposal_id,
                         title=item["title"], kind=p["kind"], vault_commit=commit)
            self._notify_submitter(p, f"Published: {item['title']}", f"Your change to \"{item['title']}\" is now live for the people "
                                   f"who may see it.\n\n{self.svc.settings.public_url}/#/knowledge?doc={item['id']}")
            self._after_publish(p, item)
            return {"status": "published", "vault_commit": commit}
        except Exception as exc:
            log.exception("publication of proposal %s failed", proposal_id)
            if switched and p["kind"] != "archive":
                self.store.restore_published(p["item_id"], previous, p["version_id"], actor)
            self.store.set_proposal_status(proposal_id, "failed", error=str(exc)[:500])
            audit.record(self.svc.ops, audit.ADMIN_ACTION, actor, self._name(actor), action="knowledge_publish_failed",
                         proposal=proposal_id, error=str(exc)[:300])
            self._notify_admins(f"Publication failed: {item['title']}", f"The previous version stays live. Reason: {exc}\n"
                                f"Retry from Approvals: {self.svc.settings.public_url}/#/approvals")
            raise

    def _verify_retrievable(self, version_id: UUID) -> None:
        """§9 step 6 "verifies retrieval success": the new version's first passage must come back from the same filtered search
        employees use (published, in effect, permitted). A version that takes effect later is checked when it does."""
        v = self.store.get_version(version_id)
        if v["effective_date"] and v["effective_date"] > date.today():
            return
        first = self.store.first_chunk(version_id)
        item = self.store.get_item(v["item_id"])
        emb = first["embedding"]
        emb = emb.to_list() if hasattr(emb, "to_list") else list(emb)
        found = self.svc.search.store.vector_search(emb, self.svc.embedder.name, frozenset(item["department_ids"]),
                                                   (PUBLISHED,), 5, levels=frozenset({item["sensitivity"]}))
        if not any(c.version_id == version_id for c in found):
            raise KnowledgeError(500, "the new version could not be found by search after publication")

    def _mark_gap_in_progress(self, gap_id: Optional[UUID]) -> None:
        gaps = getattr(self.svc, "gaps", None)
        if gap_id and gaps:
            g = gaps.get(gap_id)
            if g and g["status"] == "open":
                gaps.update(gap_id, status="in_progress")

    def _after_publish(self, p: dict, item: dict) -> None:
        """§9: "Once approved new knowledge is published, mark the gap resolved"; then the bots' confirmation hook."""
        gaps = getattr(self.svc, "gaps", None)
        if gaps and p.get("gap_id"):
            gaps.resolve_by_proposal(p["id"], p["gap_id"], None)
        hook = getattr(self.svc, "on_published", None)
        if hook:
            try:
                hook(p, item)
            except Exception:
                log.exception("after-publish hook failed")

    # ---- reading ----
    def _may_see(self, actor: Principal, item: dict) -> bool:
        if actor.all_departments:
            return True
        return bool(set(item["department_ids"]) & set(actor.department_ids) | set(item["department_ids"]) & set(actor.managed_department_ids))

    def diff(self, p: dict) -> dict:
        """Before/after for reviewers (§7 Approvals "diffs"): text lines and metadata changes."""
        before = self.store.get_version(p["base_version_id"]) if p.get("base_version_id") else None
        after = self.store.get_version(p["version_id"])
        old_text = (before["body"] or "") if before else ""
        new_text = "" if p["kind"] == "archive" else (after["body"] or "")
        lines = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), "published", "proposed", lineterm="", n=3))
        item = self.store.get_item(p["item_id"])
        meta = p.get("meta") or {}
        changes = []
        if p["kind"] == "update":
            names = {str(d["id"]): d["name"] for d in self.svc.users.list_departments()}
            cur = {"title": item["title"], "category": item["category"], "sensitivity": item["sensitivity"],
                   "departments": ", ".join(sorted(item["departments"])), "provenance": item["provenance"],
                   "owner": self._name(item["owner_id"])}
            new = {"title": meta.get("title"), "category": meta.get("category"), "sensitivity": meta.get("sensitivity"),
                   "departments": ", ".join(sorted(names.get(str(d), str(d)) for d in meta.get("department_ids") or [])) or None,
                   "provenance": meta.get("provenance"), "owner": self._name(meta.get("owner_id")) if meta.get("owner_id") else None}
            changes = [{"field": k, "from": cur[k], "to": new[k]} for k in cur if new[k] is not None and new[k] != cur[k]]
        return {"unified": lines, "metadata_changes": changes,
                "before": {"version": before["version"], "text": old_text} if before else None,
                "after": {"version": after["version"], "text": new_text}}

    # ---- notifications (email now; Telegram after the Hermes milestone) ----
    def _name(self, user_id) -> Optional[str]:
        if not user_id:
            return None
        u = self.svc.users.get(UUID(str(user_id)))
        return u["full_name"] if u else None

    def _notify_submitter(self, p: dict, subject: str, text: str) -> None:
        from ..notifications.mail import send_safely
        u = self.svc.users.get(p["submitted_by"]) if p.get("submitted_by") else None
        if u and getattr(self.svc, "mailer", None):
            send_safely(self.svc.mailer, u["email"], subject, text)
        hook = getattr(self.svc, "notify_user", None)
        if hook and u:
            hook(u, subject, text)

    def _notify_reviewers(self, proposal_id: UUID) -> None:
        from ..notifications.mail import send_safely
        p = self.store.get_proposal(proposal_id)
        if not getattr(self.svc, "mailer", None):
            return
        people = {r["email"] for r in self.svc.users.reviewers_for(self.proposal_departments(p))}
        for email in people:
            send_safely(self.svc.mailer, email, f"Review needed: {p['title']}",
                        f"A change to \"{p['title']}\" is waiting for your review.\n\n{self.svc.settings.public_url}/#/approvals")

    def _notify_admins(self, subject: str, text: str) -> None:
        from ..notifications.mail import send_safely
        if not getattr(self.svc, "mailer", None):
            return
        for u in self.svc.users.list_users(status="active"):
            if u["role"] == Role.SYSTEM_ADMIN.value:
                send_safely(self.svc.mailer, u["email"], subject, text)
