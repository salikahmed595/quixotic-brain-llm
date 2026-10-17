import pytest
from pydantic import ValidationError
from uuid import uuid4

from backend.config import Settings
from backend.permissions.access import PermissionDenied, Principal, resolve_department_scope
from backend.permissions.roles import P, Role, can
from backend.permissions.workflow import LEGAL_EDGES, check_transition
from tests.conftest import BASE, make_settings


# ---- config: no hidden defaults (CLAUDE.md Rule 1) ----
def test_missing_required_values_fail_loudly():
    with pytest.raises(ValidationError) as e:
        Settings(_env_file=None, database_url="x")
    missing = {err["loc"][0] for err in e.value.errors()}
    assert {"chunk_size", "candidate_count", "confidence_high", "generation_provider", "session_secret", "public_url",
            "mail_backend", "admin_mfa_required", "field_encryption_key", "one_time_link_ttl_seconds"} <= missing


@pytest.mark.parametrize("field,value", [("candidate_count", 19), ("candidate_count", 41), ("final_chunk_count", 4),
                                         ("final_chunk_count", 9)])
def test_prd_ranges_enforced(field, value):          # PRD §27: 20–40 candidates, 5–8 final
    with pytest.raises(ValidationError):
        make_settings(**{field: value})


def test_prd_range_bounds_accepted():
    assert make_settings(candidate_count=40, final_chunk_count=8).final_chunk_count == 8


def test_session_secret_must_be_long():
    with pytest.raises(ValidationError):
        make_settings(session_secret="short")


def test_reranker_requires_model_and_tiers_parse():
    with pytest.raises(ValidationError):
        make_settings(reranker_provider="cross-encoder")
    assert make_settings(priority_tiers_json='{"policy": 1}').priority_tiers == {"policy": 1}


# ---- roles (PRD §3, one permission per §7 admin page) ----
def test_employee_has_only_employee_actions():
    for p in (P.PROPOSE_KNOWLEDGE, P.MANAGE_DOCUMENTS, P.REVIEW_PROPOSALS, P.MANAGE_USERS, P.VIEW_KNOWLEDGE, P.MANAGE_API_KEYS):
        assert not can(Role.EMPLOYEE, p)
    for p in (P.ASK, P.VIEW_SOURCES, P.SUBMIT_FEEDBACK, P.REPORT_MISSING_INFORMATION):
        assert can(Role.EMPLOYEE, p)


def test_role_boundaries_follow_prd_3():
    assert can(Role.DEPARTMENT_REVIEWER, P.REVIEW_PROPOSALS) and not can(Role.DEPARTMENT_REVIEWER, P.MANAGE_DOCUMENTS)
    assert can(Role.KNOWLEDGE_ADMIN, P.MANAGE_DOCUMENTS) and can(Role.KNOWLEDGE_ADMIN, P.MANAGE_KNOWLEDGE_GAPS)
    assert not can(Role.KNOWLEDGE_ADMIN, P.MANAGE_USERS) and not can(Role.KNOWLEDGE_ADMIN, P.MANAGE_API_KEYS)   # no platform security
    assert all(can(Role.SYSTEM_ADMIN, p) for p in P)                    # the §4.3 admin screenshot shows every page
    assert can(Role.FOUNDER_CEO, P.REVIEW_PROPOSALS) and not can(Role.FOUNDER_CEO, P.MANAGE_USERS)


# ---- department scope applied before retrieval (PRD §42) ----
def _user(role, depts=(), managed=(), can_publish=False):
    return Principal(uuid4(), "emp_1", role, frozenset(depts), frozenset(managed), can_publish)


def test_company_wide_never_by_default():
    a, b = uuid4(), uuid4()
    assert resolve_department_scope(_user(Role.DEPARTMENT_REVIEWER, [a]), frozenset({a, b})) == {a}
    assert resolve_department_scope(_user(Role.EMPLOYEE, [a, uuid4()]), frozenset({a, b})) == {a}   # archived dept drops out


def test_scope_is_authorized_departments_only():
    sales, hr = uuid4(), uuid4()
    p = _user(Role.EMPLOYEE, [sales])
    assert resolve_department_scope(p, frozenset({sales, hr})) == {sales}
    with pytest.raises(PermissionDenied):
        resolve_department_scope(p, frozenset({sales, hr}), requested_department_id=hr)


def test_admin_sees_all_and_api_key_intersects():
    a, b = uuid4(), uuid4()
    admin = _user(Role.SYSTEM_ADMIN)
    assert resolve_department_scope(admin, frozenset({a, b})) == {a, b}
    assert resolve_department_scope(admin, frozenset({a, b}), key_allowed_department_ids=frozenset({a})) == {a}
    with pytest.raises(PermissionDenied):
        resolve_department_scope(admin, frozenset({a, b}), requested_department_id=b, key_allowed_department_ids=frozenset({a}))


# ---- approval workflow (PRD §12.3) ----
def test_workflow_chain_edges_exist_and_nothing_skips():
    assert "submitted" in LEGAL_EDGES["draft"] and "pending_review" in LEGAL_EDGES["submitted"]
    assert {"approved", "rejected"} <= LEGAL_EDGES["pending_review"] and "active" in LEGAL_EDGES["approved"]
    assert "active" not in LEGAL_EDGES["draft"] and "active" not in LEGAL_EDGES["pending_review"]
    assert "expired" not in {t for s in LEGAL_EDGES.values() for t in s}      # no PRD-defined path to expiry


def test_manager_reviews_only_managed_departments_and_only_admin_archives():
    mine, other = uuid4(), uuid4()
    m = _user(Role.DEPARTMENT_REVIEWER, [mine, other], managed=[mine])
    check_transition(m, "pending_review", "approved", [mine], None)
    check_transition(m, "approved", "active", [mine], None)
    with pytest.raises(PermissionDenied):
        check_transition(m, "pending_review", "approved", [other], None)
    with pytest.raises(PermissionDenied):
        check_transition(m, "active", "archived", [mine], None)
    check_transition(_user(Role.SYSTEM_ADMIN, can_publish=True), "active", "archived", [mine], None)


def test_illegal_edge_rejected():
    with pytest.raises(PermissionDenied):
        check_transition(_user(Role.SYSTEM_ADMIN, can_publish=True), "draft", "active", [], None)
