"""Department scope — applied BEFORE retrieval (PRD §3 deny by default, §8 retrieval workflow, §10 "filters apply before
vector/keyword retrieval")."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from .roles import ALL_DEPARTMENT_ROLES, Role


class PermissionDenied(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    """An authenticated, Active person (PRD §5 FR-AUTH-03/05: no other account state ever becomes a Principal)."""
    user_id: UUID
    employee_id: str
    role: Role
    department_ids: frozenset[UUID]                                          # member of (§3 multi-department membership)
    managed_department_ids: frozenset[UUID] = field(default_factory=frozenset)  # departments this person reviews (§7)
    can_publish: bool = False                                                # §3 Knowledge Admin publisher grant

    @property
    def all_departments(self) -> bool:
        return self.role in ALL_DEPARTMENT_ROLES


def resolve_department_scope(
    principal: Principal,
    all_department_ids: frozenset[UUID],
    requested_department_id: Optional[UUID] = None,
    key_allowed_department_ids: Optional[frozenset[UUID]] = None,
) -> frozenset[UUID]:
    """Departments whose knowledge may be retrieved for this request.

    - Knowledge Admin, System Admin, Founder/CEO: every active department (they curate or govern all knowledge).
    - Everyone else: only the departments they are a member of (§3, §6 FR-CHAT-06).
    - API key calls: intersected with the key's allowed departments.
    - A requested department outside the scope is refused, never silently widened (§6 FR-CHAT-06 tampered values).
    """
    scope = all_department_ids if principal.all_departments else principal.department_ids & all_department_ids
    if key_allowed_department_ids is not None:
        scope = scope & key_allowed_department_ids
    if requested_department_id is not None:
        if requested_department_id not in scope:
            raise PermissionDenied("department not authorized for this request")
        scope = frozenset({requested_department_id})
    return frozenset(scope)
