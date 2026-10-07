"""Knowledge approval workflow — PRD §12.3.

    Draft -> Submitted -> Pending Review -> Approved -> Active
    alternative states: Rejected, Archived, Expired

PRD §9: Contributors submit (all submissions require review); Managers approve/reject department
knowledge; Administrators approve and archive. PRD §5: nothing is auto-approved.
No transition into `expired` exists: the PRD names the state but not how items expire (docs/PRD_GAPS.md).
"""
from __future__ import annotations

from typing import Iterable
from uuid import UUID

from .access import PermissionDenied, Principal
from .roles import P, Role, can

DRAFT, SUBMITTED, PENDING, APPROVED, ACTIVE = "draft", "submitted", "pending_review", "approved", "active"
REJECTED, ARCHIVED, EXPIRED = "rejected", "archived", "expired"
STATUSES = (DRAFT, SUBMITTED, PENDING, APPROVED, ACTIVE, REJECTED, ARCHIVED, EXPIRED)

LEGAL_EDGES: dict[str, set[str]] = {
    DRAFT: {SUBMITTED, ARCHIVED},
    SUBMITTED: {PENDING, ARCHIVED},
    PENDING: {APPROVED, REJECTED, ARCHIVED},
    APPROVED: {ACTIVE, ARCHIVED},
    ACTIVE: {ARCHIVED},
    REJECTED: {ARCHIVED},
    EXPIRED: {ARCHIVED},
    ARCHIVED: set(),
}


def check_transition(
    actor: Principal, from_status: str, to_status: str,
    item_department_ids: Iterable[UUID], created_by: UUID | None,
) -> None:
    """Raise PermissionDenied unless `actor` may move a version from_status -> to_status."""
    if to_status not in LEGAL_EDGES.get(from_status, set()):
        raise PermissionDenied(f"transition {from_status} -> {to_status} is not part of the PRD §12.3 workflow")
    depts = set(item_department_ids)

    if to_status == ARCHIVED:                                   # §9.4 "Archive information"
        if not can(actor.role, P.ARCHIVE_KNOWLEDGE):
            raise PermissionDenied("only administrators can archive knowledge")
        return
    if to_status == SUBMITTED:                                  # §9.2 contributors submit
        if not can(actor.role, P.SUBMIT_INFORMATION):
            raise PermissionDenied("your role cannot submit information")
        if actor.role is not Role.ADMINISTRATOR and created_by != actor.user_id:
            raise PermissionDenied("only the author can submit a draft")
        return
    if to_status == PENDING:                                    # §12.3 step after Submitted
        return                                                  # performed by the submit action (system)
    # approve / reject / activate -> reviewers
    if can(actor.role, P.APPROVE_KNOWLEDGE):                    # §9.4
        return
    if can(actor.role, P.APPROVE_REJECT_DEPARTMENT_KNOWLEDGE) and depts & actor.managed_department_ids:
        return                                                  # §9.3 "department knowledge"
    raise PermissionDenied("only the department manager or an administrator can review this knowledge")
