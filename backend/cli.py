"""Bootstrap CLI. Every user-management route needs an administrator (PRD §9.4), so the first one is created here.

    python -m backend.cli migrate
    python -m backend.cli create-user --employee-id emp_001 --email you@your-company.com --name "Your Name" \
        --role administrator --department "Company Wide" --department Administration
(the password is read from the QB_NEW_USER_PASSWORD environment variable or prompted for)

    python -m backend.cli seed-departments
creates the departments the owner chose on 2026-10-17 (PRD §8 suggested hierarchy); existing names are left alone.
"""
from __future__ import annotations

import argparse
import getpass
import os

from .auth.security import hash_password
from .config import get_settings
from .database.pool import make_pool, migrate
from .database.users import UserStore
from .permissions.roles import Role

# PRD §8 suggested hierarchy, chosen by the owner on 2026-10-17 as the initial departments. Sales sub-teams are separate
# departments (no hierarchy in the schema). §8 "Glossary/" and "Archive/" are vault folders, not departments.
# Administrators can rename, add or disable departments later (PRD §7 Departments).
INITIAL_DEPARTMENTS = ("Company General", "HR", "Sales - Fresh Seller", "Sales - Upseller", "Production",
                       "Marketing", "Customer Support", "Leadership", "Training")


def main() -> int:
    ap = argparse.ArgumentParser(prog="backend.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    sub.add_parser("seed-departments")
    cu = sub.add_parser("create-user")
    cu.add_argument("--employee-id", required=True)
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", required=True, choices=[r.value for r in Role])
    cu.add_argument("--department", action="append", default=[], help="department name; repeatable (PRD §10)")
    a = ap.parse_args()
    settings = get_settings()
    if a.cmd == "migrate":
        print("applied:", migrate(settings.database_url) or "nothing to do")
        return 0
    migrate(settings.database_url)
    users = UserStore(make_pool(settings.database_url), settings.tenant_id)
    if a.cmd == "seed-departments":
        for name in INITIAL_DEPARTMENTS:
            print(("exists " if users.department_by_name(name) else "created"), name)
            if not users.department_by_name(name):
                users.create_department(name)
        return 0
    ids = []
    for name in a.department:
        d = users.department_by_name(name)
        if d is None:
            raise SystemExit(f"unknown department {name!r}")
        ids.append(d["id"])
    password = os.environ.get("QB_NEW_USER_PASSWORD") or getpass.getpass("Password: ")
    uid = users.create_user(a.employee_id, a.email, a.name, hash_password(password), Role(a.role), ids)
    print("created user", uid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
