"""Bootstrap CLI. Every user-management route needs an administrator (PRD §9.4), so the first one is created here.

    python -m backend.cli migrate
    python -m backend.cli create-user --employee-id emp_001 --email you@your-company.com --name "Your Name" \
        --role administrator --department "Company Wide" --department Administration
(the password is read from the QB_NEW_USER_PASSWORD environment variable or prompted for)
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


def main() -> int:
    ap = argparse.ArgumentParser(prog="backend.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
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
