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
    assert {"chunk_size", "candidate_count", "confidence_high", "generation_provider", "session_secret"} <= missing


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


# ---- roles (PRD §9) ----
def test_employee_cannot_modify_or_manage():
    for p in (P.SUBMIT_INFORMATION, P.UPLOAD_DOCUMENTS, P.APPROVE_REJECT_DEPARTMENT_KNOWLEDGE, P.MANAGE_USERS):
        assert not can(Role.EMPLOYEE, p)
    for p in (P.ASK, P.VIEW_SOURCES, P.SUBMIT_FEEDBACK, P.REPORT_INCORRECT_ANSWER):
        assert can(Role.EMPLOYEE, p)


def test_roles_are_cumulative_and_admin_has_everything():
    assert can(Role.CONTRIBUTOR, P.UPLOAD_DOCUMENTS) and not can(Role.CONTRIBUTOR, P.APPROVE_REJECT_DEPARTMENT_KNOWLEDGE)
    assert can(Role.MANAGER, P.APPROVE_REJECT_DEPARTMENT_KNOWLEDGE) and not can(Role.MANAGER, P.MANAGE_API_KEYS)
    assert all(can(Role.ADMINISTRATOR, p) for p in P)


# ---- department scope applied before retrieval (PRD §42) ----
def _user(role, depts=(), managed=()):
    return Principal(uuid4(), "emp_1", role, frozenset(depts), frozenset(managed))


def test_scope_is_authorized_departments_only():
    sales, hr = uuid4(), uuid4()
    p = _user(Role.EMPLOYEE, [sales])
    assert resolve_department_scope(p, frozenset({sales, hr})) == {sales}
    with pytest.raises(PermissionDenied):
        resolve_department_scope(p, frozenset({sales, hr}), requested_department_id=hr)


def test_admin_sees_all_and_api_key_intersects():
    a, b = uuid4(), uuid4()
    admin = _user(Role.ADMINISTRATOR)
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


def test_contributor_submits_own_draft_but_cannot_approve():
    d = uuid4()
    c = _user(Role.CONTRIBUTOR, [d])
    check_transition(c, "draft", "submitted", [d], c.user_id)
    with pytest.raises(PermissionDenied):
        check_transition(c, "draft", "submitted", [d], uuid4())             # not the author
    with pytest.raises(PermissionDenied):
        check_transition(c, "pending_review", "approved", [d], c.user_id)   # all submissions require review (§9.2)


def test_manager_reviews_only_managed_departments_and_only_admin_archives():
    mine, other = uuid4(), uuid4()
    m = _user(Role.MANAGER, [mine, other], managed=[mine])
    check_transition(m, "pending_review", "approved", [mine], None)
    check_transition(m, "approved", "active", [mine], None)
    with pytest.raises(PermissionDenied):
        check_transition(m, "pending_review", "approved", [other], None)
    with pytest.raises(PermissionDenied):
        check_transition(m, "active", "archived", [mine], None)
    check_transition(_user(Role.ADMINISTRATOR), "active", "archived", [mine], None)


def test_illegal_edge_rejected():
    with pytest.raises(PermissionDenied):
        check_transition(_user(Role.ADMINISTRATOR), "draft", "active", [], None)
