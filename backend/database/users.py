"""Users, roles and departments — PRD §9, §10, §41, §42."""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

from ..permissions.access import Principal
from ..permissions.roles import Role


class UserStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    # ---- users ----
    def get_by_login(self, identifier: str) -> Optional[dict]:
        """§41: email or employee ID."""
        with self.pool.connection() as c:
            return c.execute(
                "SELECT * FROM users WHERE tenant_id=%s AND is_active AND (lower(email)=lower(%s) OR lower(employee_id)=lower(%s))",
                (self.tenant, identifier, identifier)).fetchone()

    def get_by_login_any(self, identifier: str) -> Optional[dict]:
        """Like get_by_login but also finds accounts that are waiting for approval, rejected or disabled, so the login can
        say why it refuses (only after the right password was given)."""
        with self.pool.connection() as c:
            return c.execute(
                "SELECT * FROM users WHERE tenant_id=%s AND (lower(email)=lower(%s) OR lower(employee_id)=lower(%s))",
                (self.tenant, identifier, identifier)).fetchone()

    def get(self, user_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM users WHERE tenant_id=%s AND id=%s", (self.tenant, user_id)).fetchone()

    def get_by_employee_id(self, employee_id: str) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM users WHERE tenant_id=%s AND is_active AND employee_id=%s",
                             (self.tenant, employee_id)).fetchone()

    def principal(self, user: dict) -> Principal:
        with self.pool.connection() as c:
            depts = {r["department_id"] for r in c.execute(
                "SELECT department_id FROM user_departments WHERE user_id=%s", (user["id"],))}
            managed = {r["id"] for r in c.execute(
                "SELECT id FROM departments WHERE tenant_id=%s AND manager_id=%s", (self.tenant, user["id"]))}
        return Principal(user["id"], user["employee_id"], Role(user["role"]), frozenset(depts), frozenset(managed))

    def list_users(self) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute(
                """SELECT u.id, u.employee_id, u.email, u.full_name, u.role, u.is_active, u.created_at,
                          COALESCE(array_agg(d.name) FILTER (WHERE d.id IS NOT NULL), '{}') AS departments,
                          COALESCE(array_agg(d.id) FILTER (WHERE d.id IS NOT NULL), '{}') AS department_ids
                   FROM users u LEFT JOIN user_departments ud ON ud.user_id=u.id
                   LEFT JOIN departments d ON d.id=ud.department_id
                   WHERE u.tenant_id=%s AND u.approval_status <> 'pending' GROUP BY u.id ORDER BY u.full_name""", (self.tenant,)).fetchall()

    def create_user(self, employee_id: str, email: str, full_name: str, password_hash: str, role: Role,
                    department_ids: list[UUID]) -> UUID:
        with self.pool.connection() as c:
            uid = c.execute(
                "INSERT INTO users (tenant_id, employee_id, email, full_name, password_hash, role) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (self.tenant, employee_id, email, full_name, password_hash, role.value)).fetchone()["id"]
            for d in department_ids:
                c.execute("INSERT INTO user_departments (user_id, department_id) VALUES (%s,%s)", (uid, d))
        return uid

    def update_user(self, user_id: UUID, role: Optional[Role] = None, is_active: Optional[bool] = None,
                    department_ids: Optional[list[UUID]] = None) -> None:
        with self.pool.connection() as c:
            if role is not None:
                c.execute("UPDATE users SET role=%s WHERE tenant_id=%s AND id=%s", (role.value, self.tenant, user_id))
            if is_active is not None:
                c.execute("UPDATE users SET is_active=%s WHERE tenant_id=%s AND id=%s", (is_active, self.tenant, user_id))
            if department_ids is not None:
                c.execute("DELETE FROM user_departments WHERE user_id=%s", (user_id,))
                for d in department_ids:
                    c.execute("INSERT INTO user_departments (user_id, department_id) VALUES (%s,%s)", (user_id, d))

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

    # ---- self sign-up and approval (owner request) ----
    def username_or_email_taken(self, username: str, email: str) -> bool:
        """Also refuses a username that equals someone's email (or the reverse): both are accepted at login, so they must not clash."""
        with self.pool.connection() as c:
            return c.execute("SELECT 1 FROM users WHERE tenant_id=%s AND (lower(employee_id) IN (lower(%s), lower(%s)) "
                             "OR lower(email) IN (lower(%s), lower(%s))) LIMIT 1",
                             (self.tenant, username, email, username, email)).fetchone() is not None

    def create_pending_user(self, username: str, email: str, full_name: str, password_hash: str,
                            requested_department_id: Optional[UUID]) -> UUID:
        with self.pool.connection() as c:
            return c.execute(
                "INSERT INTO users (tenant_id, employee_id, email, full_name, password_hash, role, is_active, approval_status, "
                "requested_department_id) VALUES (%s,%s,%s,%s,%s,'employee',false,'pending',%s) RETURNING id",
                (self.tenant, username, email, full_name, password_hash, requested_department_id)).fetchone()["id"]

    def pending_requests(self, department_ids: Optional[frozenset] = None) -> list[dict]:
        """Waiting sign-ups. `department_ids` (a manager's own departments) limits the list to requests for those departments
        or for no particular department; None = all (administrator)."""
        with self.pool.connection() as c:
            rows = c.execute(
                """SELECT u.id, u.employee_id AS username, u.email, u.full_name, u.created_at, u.requested_department_id,
                          d.name AS requested_department
                   FROM users u LEFT JOIN departments d ON d.id = u.requested_department_id
                   WHERE u.tenant_id=%s AND u.approval_status='pending' ORDER BY u.created_at""", (self.tenant,)).fetchall()
        if department_ids is None:
            return rows
        return [r for r in rows if r["requested_department_id"] is None or r["requested_department_id"] in department_ids]

    def decide_request(self, user_id: UUID, approve: bool, role: Optional[Role], department_ids: list[UUID], decider: UUID) -> bool:
        """Approve (role + departments) or reject a pending sign-up. False when it is not pending any more."""
        with self.pool.connection() as c:
            ok = c.execute(
                "UPDATE users SET approval_status=%s, is_active=%s, role=COALESCE(%s, role), decided_by=%s, decided_at=now() "
                "WHERE tenant_id=%s AND id=%s AND approval_status='pending'",
                ("approved" if approve else "rejected", approve, role.value if role else None, decider, self.tenant, user_id)).rowcount > 0
            if ok and approve:
                for d in department_ids:
                    c.execute("INSERT INTO user_departments (user_id, department_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (user_id, d))
        return ok

    # ---- departments (§10: create, rename, archive, assign users, set managers) ----
    def list_departments(self, include_archived: bool = True) -> list[dict]:
        q = "SELECT * FROM departments WHERE tenant_id=%s" + ("" if include_archived else " AND status='active'")
        with self.pool.connection() as c:
            return c.execute(q + " ORDER BY name", (self.tenant,)).fetchall()

    def all_department_ids(self) -> frozenset[UUID]:
        return frozenset(d["id"] for d in self.list_departments(include_archived=False))

    def department_by_name(self, name: str) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM departments WHERE tenant_id=%s AND lower(name)=lower(%s)",
                             (self.tenant, name)).fetchone()

    def create_department(self, name: str) -> UUID:
        with self.pool.connection() as c:
            return c.execute("INSERT INTO departments (tenant_id, name) VALUES (%s,%s) RETURNING id",
                             (self.tenant, name)).fetchone()["id"]

    def update_department(self, dept_id: UUID, name: Optional[str] = None, status: Optional[str] = None,
                          manager_id: Optional[UUID] = None, clear_manager: bool = False) -> None:
        with self.pool.connection() as c:
            if name is not None:
                c.execute("UPDATE departments SET name=%s WHERE tenant_id=%s AND id=%s", (name, self.tenant, dept_id))
            if status is not None:
                c.execute("UPDATE departments SET status=%s WHERE tenant_id=%s AND id=%s", (status, self.tenant, dept_id))
            if manager_id is not None or clear_manager:
                c.execute("UPDATE departments SET manager_id=%s WHERE tenant_id=%s AND id=%s",
                          (manager_id, self.tenant, dept_id))
