"""The backend-owned "Quixotic Approvals" Telegram bot — PRD §9 steps 1, 2, 5, 6 (docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md H3).

Why a separate bot: approval must never depend on an AI model. Every tap arrives with the tapper's Telegram user id, which this
backend maps to a company user (integration_identities) and checks with the same review rules as the web (knowledge/service.py).

- Confirm / Cancel: a proposal that came through Hermes waits until its real sender confirms it here (§9 step 1/2: verified
  identity; the transcript of a voice note is shown for confirmation).
- Approve / Reject: sent to reviewers who linked Telegram; same rules as the web (department reviewers, publishers, two approvers
  for high-impact topics).
- After publication the submitter gets the version and a link (§9 step 6); a failure keeps the old version and is reported (step 7).
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from ..analytics import audit
from ..knowledge.service import KnowledgeError, KnowledgeService, may_review

log = logging.getLogger("approvals_bot")


class ApprovalsBot:
    def __init__(self, svc, bot) -> None:
        self.svc, self.bot = svc, bot

    # ---- helpers ----
    def _ks(self) -> KnowledgeService:
        return KnowledgeService(self.svc)

    def _chats(self, user_id) -> list[str]:
        return self.svc.integrations.external_ids_for(user_id, "telegram") if user_id else []

    def _link(self, path: str) -> str:
        return f"{self.svc.settings.public_url}/#/{path}"

    def _summary(self, pid: UUID, with_diff: bool = True) -> str:
        ks = self._ks()
        p = self.svc.knowledge.get_proposal(pid)
        kind = {"create": "New document", "update": "Change", "archive": "Archive", "restore": "Restore earlier version"}[p["kind"]]
        lines = [f"{kind}: {p['title']}", f"Departments: {', '.join(p['current_departments']) or '-'}"]
        if p["high_impact"]:
            lines.append(f"High impact: needs {p['required_approvals']} different approvers")
        if p.get("summary"):
            lines.append(f"Note: {p['summary']}")
        if p.get("transcript"):
            lines.append(f'Voice note heard as: "{p["transcript"][:600]}"')
        if with_diff and p["kind"] != "archive":
            diff = ks.diff(p)
            changed = [l for l in diff["unified"][2:] if l[:1] in "+-"][:24] if diff["before"] else \
                [l for l in (diff["after"]["text"] or "").splitlines() if l.strip()][:24]
            if changed:
                lines.append("")
                lines.extend(changed)
        lines.append("")
        lines.append(self._link("approvals"))
        return "\n".join(lines)

    # ---- outgoing ----
    def request_confirmation(self, pid: UUID) -> None:
        p = self.svc.knowledge.get_proposal(pid)
        for chat in self._chats(p["submitted_by"]):
            try:
                mid = self.bot.send(chat, "Please confirm you sent this to Quixotic AI. Nothing changes until it is reviewed and approved.\n\n"
                                    + self._summary(pid), [[("Confirm", f"c:{pid}"), ("Cancel", f"x:{pid}")]])
                self.svc.integrations.save_message(pid, chat, mid, "confirm")
            except Exception:
                log.exception("could not send the confirmation request")

    def notify_reviewers(self, pid: UUID) -> None:
        p = self.svc.knowledge.get_proposal(pid)
        depts = self._ks().proposal_departments(p)
        for ident in self.svc.integrations.identities("telegram"):
            if ident["account_status"] != "active":
                continue
            user = self.svc.users.get(ident["user_id"])
            principal = self.svc.users.principal(user)
            if not may_review(principal, depts):
                continue
            try:
                mid = self.bot.send(ident["external_id"], "Review needed\n\n" + self._summary(pid),
                                    [[("Approve", f"a:{pid}"), ("Reject", f"r:{pid}")]])
                self.svc.integrations.save_message(pid, ident["external_id"], mid, "review")
            except Exception:
                log.exception("could not send a review request")

    def notify_user(self, user: dict, subject: str, text: str) -> None:
        for chat in self._chats(user["id"]):
            try:
                self.bot.send(chat, f"{subject}\n\n{text}")
            except Exception:
                log.exception("could not notify a user on Telegram")

    def notify_department(self, department_id: Optional[UUID], text: str) -> None:
        """New knowledge gap for a department's reviewers (§9 gap loop: "Admin may notify the authorized owner on Telegram")."""
        if not department_id:
            return
        for r in self.svc.users.reviewers_for([department_id]):
            self.notify_user({"id": r["id"]}, "Question without an approved answer", text)

    def _close_buttons(self, pid: UUID, purpose: Optional[str] = None) -> None:
        for m in self.svc.integrations.messages_for(pid):
            if purpose is None or m["purpose"] == purpose:
                self.bot.clear_buttons(m["chat_id"], m["message_id"])

    # ---- incoming ----
    def handle_update(self, update: dict) -> None:
        uid = update.get("update_id")
        if uid is not None and not self.svc.integrations.record_event("telegram_approvals", str(uid), "update"):
            return                                                           # duplicate delivery (§12)
        if "callback_query" in update:
            self._callback(update["callback_query"])
        elif "message" in update:
            self._message(update["message"])

    def _message(self, msg: dict) -> None:
        sender = str(msg.get("from", {}).get("id", ""))
        chat = str(msg.get("chat", {}).get("id", sender))
        text = (msg.get("text") or "").strip()
        user = self.svc.integrations.user_for("telegram", sender)
        if text.startswith("/start") or text.startswith("/id"):
            self.bot.send(chat, f"Your Telegram ID is {sender}.\n" + (f"It is linked to {user['full_name']}." if user else
                          "It is not linked to a Quixotic AI account yet: give this number to your administrator "
                          "(System → Integrations)."))
        elif text.startswith("/pending") and user:
            principal = self.svc.users.principal(user)
            ks = self._ks()
            waiting = [p for p in self.svc.knowledge.list_proposals(["open"]) if may_review(principal, ks.proposal_departments(p))]
            if not waiting:
                self.bot.send(chat, "Nothing is waiting for your review.")
            for p in waiting[:10]:
                mid = self.bot.send(chat, "Review needed\n\n" + self._summary(p["id"]), [[("Approve", f"a:{p['id']}"), ("Reject", f"r:{p['id']}")]])
                self.svc.integrations.save_message(p["id"], chat, mid, "review")
        else:
            self.bot.send(chat, "This bot only handles confirmations and approvals. To add or change knowledge, message Quixotic Hermes.")

    def _callback(self, cq: dict) -> None:
        cid = cq.get("id", "")
        sender = str(cq.get("from", {}).get("id", ""))
        data = cq.get("data") or ""
        action, _, raw = data.partition(":")
        try:
            pid = UUID(raw)
        except ValueError:
            self.bot.answer_callback(cid, "Unknown button")
            return
        user = self.svc.integrations.user_for("telegram", sender)          # the TAPPER, verified by Telegram (§9 step 1)
        if user is None:
            self.bot.answer_callback(cid, "Your Telegram account is not linked to an active Quixotic AI account.")
            return
        principal = self.svc.users.principal(user)
        p = self.svc.knowledge.get_proposal(pid)
        if p is None:
            self.bot.answer_callback(cid, "This change no longer exists.")
            return
        try:
            if action in ("c", "x"):
                if p["submitted_by"] != user["id"]:
                    self.bot.answer_callback(cid, "Only the person who sent this can confirm it.")
                    return
                if action == "c":
                    if not self.svc.knowledge.set_proposal_status(pid, "open", expect=("awaiting_confirmation",)):
                        self.bot.answer_callback(cid, "Already handled.")
                        return
                    audit.record(self.svc.ops, audit.KNOWLEDGE_SUBMISSION, user["id"], user["employee_id"], proposal=pid,
                                 action="confirmed_in_telegram")
                    self._close_buttons(pid, "confirm")
                    self.bot.answer_callback(cid, "Sent for review.")
                    self._ks()._notify_reviewers(pid)
                else:
                    if self.svc.knowledge.set_proposal_status(pid, "withdrawn", expect=("awaiting_confirmation",)):
                        self.svc.knowledge.set_status(p["version_id"], "draft", user["id"], "cancelled in Telegram")
                    self._close_buttons(pid, "confirm")
                    self.bot.answer_callback(cid, "Cancelled. Nothing was changed.")
                return
            if action in ("a", "r"):
                decision = "approve" if action == "a" else "reject"
                res = self._ks().decide(principal, pid, decision, None if decision == "approve" else f"Rejected in Telegram by {user['full_name']}",
                                        via="telegram")
                if res["status"] == "open":
                    self.bot.answer_callback(cid, "Approval recorded. Still needs " + " and ".join(res.get("waiting_for", [])))
                    for m in self.svc.integrations.messages_for(pid):
                        if m["purpose"] == "review" and str(m["chat_id"]) == sender:
                            self.bot.clear_buttons(m["chat_id"], m["message_id"])
                else:
                    self._close_buttons(pid, "review")
                    self.bot.answer_callback(cid, "Approved. Publishing now." if res["status"] == "approved" else "Rejected.")
                return
            self.bot.answer_callback(cid, "Unknown button")
        except KnowledgeError as e:
            self.bot.answer_callback(cid, str(e))
