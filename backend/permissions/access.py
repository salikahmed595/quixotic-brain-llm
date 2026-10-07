"""Department scope — applied BEFORE retrieval (PRD §42, §11.3, §51 "Access filtering before retrieval")."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from .roles import Role


class PermissionDenied(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    """An authenticated employee. PRD §11.3: detect identity, role and department."""
    user_id: UUID
    employee_id: str
    role: Role
    department_ids: frozenset[UUID]                       # authorized departments (§9.1)
    managed_department_ids: frozenset[UUID] = field(default_factory=frozenset)  # §10 "department managers"


def resolve_department_scope(
    principal: Principal,
    all_department_ids: frozenset[UUID],
    requested_department_id: Optional[UUID] = None,
    key_allowed_department_ids: Optional[frozenset[UUID]] = None,
) -> frozenset[UUID]:
    """Departments whose knowledge may be retrieved for this request.

    - Administrator: "Full access" (§9.4) -> every department.
    - Everyone else: only departments they are authorized for (§9.1 "authorized departments").
    - API key calls (§40 "Allowed departments"): intersect with the key's allowed departments.
    - A requested department outside the scope is refused, never silently widened.
    """
    scope = all_department_ids if principal.role is Role.ADMINISTRATOR else principal.department_ids
    if key_allowed_department_ids is not None:
        scope = scope & key_allowed_department_ids
    if requested_department_id is not None:
        if requested_department_id not in scope:
            raise PermissionDenied("department not authorized for this request")
        scope = frozenset({requested_department_id})
    return frozenset(scope)
