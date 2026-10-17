"""Users, account states, roles and departments — PRD §3, §5, §7 (Users, Access requests, Departments)."""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

from ..permissions.access import Principal
from ..permissions.roles import Role

# PRD §5 FR-AUTH-05
PENDING, ACTIVE, REJECTED, SUSPENDED, DEACTIVATED = "pending", "active", "rejected", "suspended", "deactivated"
ACCOUNT_STATES = (PENDING, ACTIVE, REJECTED, SUSPENDED, DEACTIVATED)
# Which state changes an administrator may make from the Users page (approval/rejection go through Access requests).
ADMIN_STATE_EDGES = {ACTIVE: {SUSPENDED, DEACTIVATED}, SUSPENDED: {ACTIVE, DEACTIVATED}, DEACTIVATED: {ACTIVE},
                     REJECTED: set(), PENDING: set()}

_USER_LIST = """
SELECT u.id, u.employee_id, u.email, u.full_name, u.phone, u.role, u.account_status, u.can_publish, u.created_at,
       u.last_login_at, u.email_verified_at, u.mfa_enabled_at IS NOT NULL AS mfa_enabled, u.decided_at, u.decision_note,
       COALESCE(array_agg(d.name ORDER BY d.name) FILTER (WHERE d.id IS NOT NULL), '{}') AS departments,
       COALESCE(array_agg(d.id ORDER BY d.name) FILTER (WHERE d.id IS NOT NULL), '{}') AS department_ids
FROM users u LEFT JOIN user_departments ud ON ud.user_id=u.id
LEFT JOIN departments d ON d.id=ud.department_id
"""


class UserStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    # ---- users ----
    def get_by_login(self, identifier: str) -> Optional[dict]:
        """Email or username, whatever the account state (the login decides what to tell the person)."""
        with self.pool.connection() as c:
            return c.execute(
                "SELECT * FROM users WHERE tenant_id=%s AND (lower(email)=lower(%s) OR lower(employee_id)=lower(%s))",
                (self.tenant, identifier, identifier)).fetchone()

    get_by_login_any = get_by_login

    def get(self, user_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM users WHERE tenant_id=%s AND id=%s", (self.tenant, user_id)).fetchone()

    def get_by_employee_id(self, employee_id: str) -> Optional[dict]:
        """Active users only (used by API-key calls acting for an employee)."""
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM users WHERE tenant_id=%s AND account_status='active' AND employee_id=%s",
                             (self.tenant, employee_id)).fetchone()

    def get_by_email(self, email: str) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM users WHERE tenant_id=%s AND lower(email)=lower(%s)", (self.tenant, email)).fetchone()

    def principal(self, user: dict) -> Principal:
        with self.pool.connection() as c:
            depts = {r["department_id"] for r in c.execute(
                "SELECT department_id FROM user_departments WHERE user_id=%s", (user["id"],))}
            reviewed = {r["department_id"] for r in c.execute(
                "SELECT department_id FROM department_reviewers WHERE user_id=%s", (user["id"],))}
        return Principal(user["id"], user["employee_id"], Role(user["role"]), frozenset(depts), frozenset(reviewed),
                         bool(user.get("can_publish")))

    def list_users(self, query: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
        where, params = ["u.tenant_id=%(t)s"], {"t": self.tenant}
        if status:
            where.append("u.account_status=%(s)s"); params["s"] = status
        else:
            where.append("u.account_status <> 'pending'")
        if query:
            where.append("(u.full_name ILIKE %(q)s OR u.email ILIKE %(q)s OR u.employee_id ILIKE %(q)s)")
            params["q"] = f"%{query}%"
        with self.pool.connection() as c:
            return c.execute(_USER_LIST + " WHERE " + " AND ".join(where) + " GROUP BY u.id ORDER BY u.full_name", params).fetchall()

    def user_row(self, user_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute(_USER_LIST + " WHERE u.tenant_id=%s AND u.id=%s GROUP BY u.id", (self.tenant, user_id)).fetchone()

    def create_user(self, employee_id: str, email: str, full_name: str, password_hash: str, role: Role,
                    department_ids: list[UUID], actor: Optional[UUID] = None, can_publish: bool = False) -> UUID:
        """An account made by an administrator (or the bootstrap CLI): Active and email treated as verified. A System Admin
        always holds the publisher grant (PRD §3 / §4.3: full administrator)."""
        can_publish = can_publish or role is Role.SYSTEM_ADMIN
        with self.pool.connection() as c, c.transaction():
            uid = c.execute(
                "INSERT INTO users (tenant_id, employee_id, email, full_name, password_hash, role, account_status, "
                "email_verified_at, can_publish) VALUES (%s,%s,%s,%s,%s,%s,'active',now(),%s) RETURNING id",
                (self.tenant, employee_id, email, full_name, password_hash, role.value, can_publish)).fetchone()["id"]
            for d in department_ids:
                c.execute("INSERT INTO user_departments (user_id, department_id) VALUES (%s,%s)", (uid, d))
            c.execute("INSERT INTO account_status_history (user_id, from_status, to_status, actor_id, note) "
                      "VALUES (%s,NULL,'active',%s,'created by an administrator')", (uid, actor))
        return uid

    def update_user(self, user_id: UUID, role: Optional[Role] = None, department_ids: Optional[list[UUID]] = None,
                    can_publish: Optional[bool] = None, full_name: Optional[str] = None) -> None:
        with self.pool.connection() as c, c.transaction():
            if role is not None:
                c.execute("UPDATE users SET role=%s WHERE tenant_id=%s AND id=%s", (role.value, self.tenant, user_id))
            if can_publish is not None:
                c.execute("UPDATE users SET can_publish=%s WHERE tenant_id=%s AND id=%s", (can_publish, self.tenant, user_id))
            if full_name is not None:
                c.execute("UPDATE users SET full_name=%s WHERE tenant_id=%s AND id=%s", (full_name, self.tenant, user_id))
            if department_ids is not None:
                c.execute("DELETE FROM user_departments WHERE user_id=%s", (user_id,))
                for d in department_ids:
                    c.execute("INSERT INTO user_departments (user_id, department_id) VALUES (%s,%s)", (user_id, d))

    def set_status(self, user_id: UUID, to_status: str, actor: Optional[UUID], note: Optional[str] = None,
                   expect: Optional[set] = None) -> Optional[str]:
        """Change the account state and record it (FR-AUTH-07). Returns the previous state, or None when the user does not
        exist or is not in one of the `expect`ed states (so two admins cannot both decide the same request)."""
        if to_status not in ACCOUNT_STATES:
            raise ValueError(to_status)
        with self.pool.connection() as c, c.transaction():
            row = c.execute("SELECT account_status FROM users WHERE tenant_id=%s AND id=%s FOR UPDATE", (self.tenant, user_id)).fetchone()
            if not row or (expect is not None and row["account_status"] not in expect):
                return None
            c.execute("UPDATE users SET account_status=%s WHERE id=%s", (to_status, user_id))
            c.execute("INSERT INTO account_status_history (user_id, from_status, to_status, actor_id, note) VALUES (%s,%s,%s,%s,%s)",
                      (user_id, row["account_status"], to_status, actor, note))
        return row["account_status"]

    def status_history(self, user_id: UUID) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT h.from_status, h.to_status, h.note, h.at, a.full_name AS actor "
                             "FROM account_status_history h LEFT JOIN users a ON a.id=h.actor_id "
                             "WHERE h.user_id=%s ORDER BY h.at, h.id", (user_id,)).fetchall()

    def mark_email_verified(self, user_id: UUID) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE users SET email_verified_at=COALESCE(email_verified_at, now()) WHERE id=%s", (user_id,))

    def record_login(self, user_id: UUID) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE users SET last_login_at=now() WHERE id=%s", (user_id,))

    def set_mfa(self, user_id: UUID, secret_enc: Optional[str], enabled: bool) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE users SET mfa_secret_enc=%s, mfa_enabled_at=CASE WHEN %s THEN now() ELSE NULL END WHERE id=%s",
                      (secret_enc, enabled, user_id))

    def system_admin_exists(self) -> bool:
        with self.pool.connection() as c:
            return c.execute("SELECT 1 FROM users WHERE tenant_id=%s AND role='system_admin' LIMIT 1", (self.tenant,)).fetchone() is not None

    # ---- own profile, preferences and password (owner request) ----
    def update_profile(self, user_id: UUID, full_name: Optional[str] = None, avatar: Optional[str] = None,
                       clear_avatar: bool = False) -> None:
        with self.pool.connection() as c:
            if full_name is not None:
                c.execute("UPDATE users SET full_name=%s WHERE tenant_id=%s AND id=%s", (full_name, self.tenant, user_id))
            if clear_avatar:
                c.execute("UPDATE users SET avatar=NULL WHERE tenant_id=%s AND id=%s", (self.tenant, user_id))
            elif avatar is not None:
                c.execute("UPDATE users SET avatar=%s WHERE tenant_id=%s AND id=%s", (avatar, self.tenant, user_id))

    def set_preferences(self, user_id: UUID, preferences: dict) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE users SET preferences=%s::jsonb WHERE tenant_id=%s AND id=%s",
                      (json.dumps(preferences), self.tenant, user_id))

    def set_password_hash(self, user_id: UUID, password_hash: str) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE users SET password_hash=%s WHERE tenant_id=%s AND id=%s", (password_hash, self.tenant, user_id))

    def bulk_departments(self, user_ids: list[UUID], add: list[UUID], remove: list[UUID]) -> int:
        """Add and/or remove department access for many users at once. Returns how many users exist among `user_ids`."""
        with self.pool.connection() as c:
            ids = [r["id"] for r in c.execute("SELECT id FROM users WHERE tenant_id=%s AND id = ANY(%s)", (self.tenant, user_ids))]
            for uid in ids:
                for d in add:
                    c.execute("INSERT INTO user_departments (user_id, department_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (uid, d))
                if remove:
                    c.execute("DELETE FROM user_departments WHERE user_id=%s AND department_id = ANY(%s)", (uid, remove))
        return len(ids)

    # ---- self sign-up and access requests (PRD §5 FR-AUTH-01..04) ----
    def username_or_email_taken(self, username: str, email: str) -> bool:
        """Also refuses a username that equals someone's email (or the reverse): both are accepted at login, so they must not clash."""
        with self.pool.connection() as c:
            return c.execute("SELECT 1 FROM users WHERE tenant_id=%s AND (lower(employee_id) IN (lower(%s), lower(%s)) "
                             "OR lower(email) IN (lower(%s), lower(%s))) LIMIT 1",
                             (self.tenant, username, email, username, email)).fetchone() is not None

    def create_pending_user(self, username: str, email: str, full_name: str, password_hash: str,
                            requested_department_id: Optional[UUID], phone: Optional[str] = None) -> UUID:
        """FR-AUTH-03: every self-registered account starts Pending, as an Employee (no role self-selection, FR-AUTH-01)."""
        with self.pool.connection() as c, c.transaction():
            uid = c.execute(
                "INSERT INTO users (tenant_id, employee_id, email, full_name, password_hash, role, account_status, "
                "requested_department_id, phone) VALUES (%s,%s,%s,%s,%s,'employee','pending',%s,%s) RETURNING id",
                (self.tenant, username, email, full_name, password_hash, requested_department_id, phone)).fetchone()["id"]
            c.execute("INSERT INTO account_status_history (user_id, from_status, to_status, note) "
                      "VALUES (%s,NULL,'pending','signed up')", (uid,))
        return uid

    def pending_requests(self) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute(
                """SELECT u.id, u.employee_id AS username, u.email, u.full_name, u.phone, u.created_at, u.email_verified_at,
                          u.requested_department_id, d.name AS requested_department
                   FROM users u LEFT JOIN departments d ON d.id = u.requested_department_id
                   WHERE u.tenant_id=%s AND u.account_status='pending' ORDER BY u.created_at""", (self.tenant,)).fetchall()

    def decide_request(self, user_id: UUID, approve: bool, role: Optional[Role], department_ids: list[UUID], decider: UUID,
                       note: Optional[str] = None) -> bool:
        """FR-AUTH-04: approve (role + departments) or reject a pending sign-up, with an optional note. False when it is not
        pending any more."""
        with self.pool.connection() as c, c.transaction():
            row = c.execute("SELECT account_status FROM users WHERE tenant_id=%s AND id=%s FOR UPDATE", (self.tenant, user_id)).fetchone()
            if not row or row["account_status"] != PENDING:
                return False
            to = ACTIVE if approve else REJECTED
            c.execute("UPDATE users SET account_status=%s, role=COALESCE(%s, role), decided_by=%s, decided_at=now(), decision_note=%s "
                      "WHERE id=%s", (to, role.value if role else None, decider, note, user_id))
            c.execute("INSERT INTO account_status_history (user_id, from_status, to_status, actor_id, note) VALUES (%s,'pending',%s,%s,%s)",
                      (user_id, to, decider, note))
            if approve:
                for d in department_ids:
                    c.execute("INSERT INTO user_departments (user_id, department_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (user_id, d))
        return True

    def counts_by_status(self) -> dict:
        with self.pool.connection() as c:
            return {r["account_status"]: r["n"] for r in c.execute(
                "SELECT account_status, count(*) AS n FROM users WHERE tenant_id=%s GROUP BY account_status", (self.tenant,))}

    # ---- departments (PRD §7 Departments: create/edit/disable; members, reviewers, document owners) ----
    def list_departments(self, include_archived: bool = True) -> list[dict]:
        q = ("SELECT d.*, COALESCE((SELECT array_agg(r.user_id) FROM department_reviewers r WHERE r.department_id=d.id), '{}') AS reviewer_ids, "
             "(SELECT count(*) FROM user_departments ud JOIN users u ON u.id=ud.user_id "
             " WHERE ud.department_id=d.id AND u.account_status='active') AS member_count "
             "FROM departments d WHERE d.tenant_id=%s" + ("" if include_archived else " AND d.status='active'"))
        with self.pool.connection() as c:
            return c.execute(q + " ORDER BY d.name", (self.tenant,)).fetchall()

    def all_department_ids(self) -> frozenset[UUID]:
        with self.pool.connection() as c:
            return frozenset(r["id"] for r in c.execute("SELECT id FROM departments WHERE tenant_id=%s AND status='active'", (self.tenant,)))

    def department_by_name(self, name: str) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM departments WHERE tenant_id=%s AND lower(name)=lower(%s)",
                             (self.tenant, name)).fetchone()

    def create_department(self, name: str, description: Optional[str] = None) -> UUID:
        with self.pool.connection() as c:
            return c.execute("INSERT INTO departments (tenant_id, name, description) VALUES (%s,%s,%s) RETURNING id",
                             (self.tenant, name, description)).fetchone()["id"]

    def update_department(self, dept_id: UUID, name: Optional[str] = None, status: Optional[str] = None,
                          description: Optional[str] = None, reviewer_ids: Optional[list[UUID]] = None) -> None:
        with self.pool.connection() as c, c.transaction():
            if name is not None:
                c.execute("UPDATE departments SET name=%s WHERE tenant_id=%s AND id=%s", (name, self.tenant, dept_id))
            if status is not None:
                c.execute("UPDATE departments SET status=%s WHERE tenant_id=%s AND id=%s", (status, self.tenant, dept_id))
            if description is not None:
                c.execute("UPDATE departments SET description=%s WHERE tenant_id=%s AND id=%s", (description, self.tenant, dept_id))
            if reviewer_ids is not None:
                c.execute("DELETE FROM department_reviewers WHERE department_id=%s", (dept_id,))
                for u in reviewer_ids:
                    c.execute("INSERT INTO department_reviewers (department_id, user_id) VALUES (%s,%s)", (dept_id, u))

    def department_members(self, dept_id: UUID) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT u.id, u.full_name, u.email, u.role, u.account_status FROM user_departments ud "
                             "JOIN users u ON u.id=ud.user_id WHERE ud.department_id=%s ORDER BY u.full_name", (dept_id,)).fetchall()

    def reviewers_for(self, department_ids) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT DISTINCT u.id, u.full_name, u.email FROM department_reviewers r JOIN users u ON u.id=r.user_id "
                             "WHERE r.department_id = ANY(%s) AND u.account_status='active'", (list(department_ids),)).fetchall()
