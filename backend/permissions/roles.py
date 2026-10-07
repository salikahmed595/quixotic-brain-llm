"""Roles and permissions — PRD §9 (and §42 RBAC). Capabilities below are copied from §9.1–§9.4.

Note: §9.1 "Use sales recommendations if permitted" is NOT a role capability here. Whether it is
permitted is decided by department authorization on sales memories (see docs/PRD_GAPS.md).
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    EMPLOYEE = "employee"            # §9.1
    CONTRIBUTOR = "contributor"      # §9.2
    MANAGER = "manager"              # §9.3
    ADMINISTRATOR = "administrator"  # §9.4


class P(str, Enum):
    # §9.1 Employee
    ASK = "ask"
    VIEW_SOURCES = "view_sources"
    SUBMIT_FEEDBACK = "submit_feedback"
    REPORT_INCORRECT_ANSWER = "report_incorrect_answer"
    # §9.2 Contributor
    SUBMIT_INFORMATION = "submit_information"
    UPLOAD_DOCUMENTS = "upload_documents"
    SUGGEST_CORRECTIONS = "suggest_corrections"
    SUBMIT_MISSING_KNOWLEDGE = "submit_missing_knowledge"
    # §9.3 Manager
    REVIEW_DEPARTMENT_SUBMISSIONS = "review_department_submissions"
    APPROVE_REJECT_DEPARTMENT_KNOWLEDGE = "approve_reject_department_knowledge"
    VIEW_DEPARTMENT_ANALYTICS = "view_department_analytics"
    VIEW_DEPARTMENT_USAGE = "view_department_usage"
    VIEW_DEPARTMENT_SALES_INSIGHTS = "view_department_sales_insights"
    # §9.4 Administrator
    MANAGE_USERS = "manage_users"
    MANAGE_DEPARTMENTS = "manage_departments"
    APPROVE_KNOWLEDGE = "approve_knowledge"
    ARCHIVE_KNOWLEDGE = "archive_knowledge"
    IMPORT_HISTORICAL_DATA = "import_historical_data"
    MANAGE_API_KEYS = "manage_api_keys"
    MANAGE_PERMISSIONS = "manage_permissions"
    CONFIGURE_MODELS = "configure_models"
    VIEW_SYSTEM_HEALTH = "view_system_health"
    VIEW_FAILED_QUERIES = "view_failed_queries"
    MANAGE_VERSIONING = "manage_versioning"
    VIEW_ALL_ANALYTICS = "view_all_analytics"
    MANAGE_VOCABULARY = "manage_vocabulary"        # owner request: teach Urdu / Roman Urdu words (administrators)


_EMPLOYEE = {P.ASK, P.VIEW_SOURCES, P.SUBMIT_FEEDBACK, P.REPORT_INCORRECT_ANSWER}
_CONTRIBUTOR = _EMPLOYEE | {P.SUBMIT_INFORMATION, P.UPLOAD_DOCUMENTS, P.SUGGEST_CORRECTIONS, P.SUBMIT_MISSING_KNOWLEDGE}
_MANAGER = _CONTRIBUTOR | {
    P.REVIEW_DEPARTMENT_SUBMISSIONS, P.APPROVE_REJECT_DEPARTMENT_KNOWLEDGE, P.VIEW_DEPARTMENT_ANALYTICS,
    P.VIEW_DEPARTMENT_USAGE, P.VIEW_DEPARTMENT_SALES_INSIGHTS,
}
_ADMIN = set(P)  # §9.4 "Full access"

ROLE_PERMISSIONS: dict[Role, frozenset[P]] = {
    Role.EMPLOYEE: frozenset(_EMPLOYEE),
    Role.CONTRIBUTOR: frozenset(_CONTRIBUTOR),
    Role.MANAGER: frozenset(_MANAGER),
    Role.ADMINISTRATOR: frozenset(_ADMIN),
}


def can(role: Role, permission: P) -> bool:
    return permission in ROLE_PERMISSIONS[role]
