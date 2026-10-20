"""Audit events — exactly the list in PRD §53."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

USER_LOGIN = "user_login"
DOCUMENT_UPLOAD = "document_upload"
KNOWLEDGE_SUBMISSION = "knowledge_submission"
APPROVAL = "approval"
REJECTION = "rejection"
ARCHIVE_EVENT = "archive_event"
PERMISSION_CHANGE = "permission_change"
API_KEY_CREATION = "api_key_creation"
MODEL_CHANGE = "model_change"
ADMIN_ACTION = "admin_action"
TRANSLATION = "translation"                 # Translate for client (owner addition; the text is never stored)
FAILED_AUTHENTICATION = "failed_authentication"
SENSITIVE_ACCESS = "sensitive_access_event"
EVENTS = {USER_LOGIN, DOCUMENT_UPLOAD, KNOWLEDGE_SUBMISSION, APPROVAL, REJECTION, ARCHIVE_EVENT, PERMISSION_CHANGE,
          API_KEY_CREATION, MODEL_CHANGE, ADMIN_ACTION, FAILED_AUTHENTICATION, SENSITIVE_ACCESS,
          TRANSLATION}                                 # TRANSLATION: owner-approved addition 2026-10-20 (docs/PRD_GAPS.md §0)


def record(ops, event: str, actor_id: Optional[UUID] = None, actor_label: Optional[str] = None, **detail) -> None:
    if event not in EVENTS:
        raise ValueError(f"{event!r} is not an audit event listed in PRD §53")
    ops.audit(event, actor_id, actor_label, {k: str(v) if isinstance(v, UUID) else v for k, v in detail.items()})
