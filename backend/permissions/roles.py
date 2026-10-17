"""Roles and permissions — PRD §3 (roles and boundaries) and §7 (one permission per admin page).

Deny by default: a role has exactly the permissions listed here; the server checks them on every call (PRD §3).
Where §3 is silent (which admin pages each role opens) the choice is recorded in docs/PRD_GAPS.md §0.1.
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    EMPLOYEE = "employee"                        # §3 Employee
    DEPARTMENT_REVIEWER = "department_reviewer"  # §3 Department Manager / Knowledge Reviewer
    KNOWLEDGE_ADMIN = "knowledge_admin"          # §3 Knowledge Admin
    SYSTEM_ADMIN = "system_admin"                # §3 System Admin
    FOUNDER_CEO = "founder_ceo"                  # §3 Founder / CEO (leadership authority)


ROLE_LABELS = {Role.EMPLOYEE: "Employee", Role.DEPARTMENT_REVIEWER: "Department Reviewer",
               Role.KNOWLEDGE_ADMIN: "Knowledge Admin", Role.SYSTEM_ADMIN: "Administrator",
               Role.FOUNDER_CEO: "Founder / CEO"}


class P(str, Enum):
    # §3 Employee
    ASK = "ask"
    VIEW_SOURCES = "view_sources"
    SUBMIT_FEEDBACK = "submit_feedback"
    REPORT_MISSING_INFORMATION = "report_missing_information"     # §6 FR-CHAT-04
    # §7 admin pages
    VIEW_KNOWLEDGE = "view_knowledge"            # Knowledge
    PROPOSE_KNOWLEDGE = "propose_knowledge"      # Add information
    MANAGE_DOCUMENTS = "manage_documents"        # Documents (upload, archive, reindex, versions)
    MANAGE_SALES_MEMORY = "manage_sales_memory"  # Sales memory
    REVIEW_PROPOSALS = "review_proposals"        # Approvals (department-scoped for reviewers)
    MANAGE_KNOWLEDGE_GAPS = "manage_knowledge_gaps"
    VIEW_DASHBOARD = "view_dashboard"            # Dashboard
    VIEW_INSIGHTS = "view_insights"              # Insights (aggregate only, §6 FR-CHAT-09)
    MANAGE_USERS = "manage_users"                # Users + Access requests
    MANAGE_DEPARTMENTS = "manage_departments"    # Departments
    MANAGE_VOCABULARY = "manage_vocabulary"      # Vocabulary
    MANAGE_API_KEYS = "manage_api_keys"          # API keys
    MANAGE_SYSTEM = "manage_system"              # System (models, indexing jobs, integrations, audit export)


_EMPLOYEE = {P.ASK, P.VIEW_SOURCES, P.SUBMIT_FEEDBACK, P.REPORT_MISSING_INFORMATION}
# §3: "All employee actions plus review assigned department's proposed updates"
_REVIEWER = _EMPLOYEE | {P.VIEW_KNOWLEDGE, P.REVIEW_PROPOSALS}
# §3: "Curate documents, proposals, taxonomy, knowledge gaps; publish when granted publisher permission"
_KNOWLEDGE_ADMIN = _REVIEWER | {P.PROPOSE_KNOWLEDGE, P.MANAGE_DOCUMENTS, P.MANAGE_SALES_MEMORY, P.MANAGE_KNOWLEDGE_GAPS,
                                P.MANAGE_VOCABULARY, P.VIEW_DASHBOARD, P.VIEW_INSIGHTS}
# §3: users, departments, roles, access, indexing, configuration, logs, integrations. The §4.3 admin screenshot shows every
# page, so the System Admin also opens the knowledge pages (docs/PRD_GAPS.md §0.1).
_SYSTEM_ADMIN = set(P)
# §3: "Submit policy proposals ... and approve governed changes within specified approval matrix"
_FOUNDER = _EMPLOYEE | {P.VIEW_KNOWLEDGE, P.PROPOSE_KNOWLEDGE, P.REVIEW_PROPOSALS, P.VIEW_DASHBOARD, P.VIEW_INSIGHTS}

ROLE_PERMISSIONS: dict[Role, frozenset[P]] = {
    Role.EMPLOYEE: frozenset(_EMPLOYEE),
    Role.DEPARTMENT_REVIEWER: frozenset(_REVIEWER),
    Role.KNOWLEDGE_ADMIN: frozenset(_KNOWLEDGE_ADMIN),
    Role.SYSTEM_ADMIN: frozenset(_SYSTEM_ADMIN),
    Role.FOUNDER_CEO: frozenset(_FOUNDER),
}

# Roles that see knowledge from every department (they curate or govern all of it). Everyone else sees only their own
# departments; "Company Wide" is never given by default (§4.2, §15).
ALL_DEPARTMENT_ROLES = frozenset({Role.KNOWLEDGE_ADMIN, Role.SYSTEM_ADMIN, Role.FOUNDER_CEO})
# §5 FR-AUTH-06 "admin MFA": every role that opens the admin layout with write access to people, knowledge or settings.
MFA_ROLES = frozenset({Role.KNOWLEDGE_ADMIN, Role.SYSTEM_ADMIN, Role.FOUNDER_CEO})
# Roles a person may never give themselves; signup always creates an Employee (§5 FR-AUTH-01).
LEADERSHIP_ROLES = frozenset({Role.SYSTEM_ADMIN, Role.FOUNDER_CEO})


def can(role: Role, permission: P) -> bool:
    return permission in ROLE_PERMISSIONS[role]


def permissions_of(role: Role) -> list[str]:
    return sorted(p.value for p in ROLE_PERMISSIONS[role])
