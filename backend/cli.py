"""Bootstrap CLI. Every user-management route needs an administrator (PRD §9.4), so the first one is created here.

    python -m backend.cli migrate
    python -m backend.cli create-user --employee-id emp_001 --email you@your-company.com --name "Your Name" \
        --role administrator --department "Company Wide" --department Administration
(the password is read from the QB_NEW_USER_PASSWORD environment variable or prompted for)

    python -m backend.cli seed-departments
creates the departments the owner chose on 2026-10-17 (PRD §8 suggested hierarchy); existing names are left alone.

    python -m backend.cli bootstrap-admin --email you@company.com --name "Your Name" --username you
PRD §5 FR-AUTH-06: the one-time protected setup path for the FIRST System Admin. It runs only on the server (shell access is
the protection) and refuses once any System Admin exists; public sign-up can never create one.
"""
from __future__ import annotations

import argparse
import getpass
import os

from .auth.security import hash_password, password_problem
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
    sub.add_parser("telegram-webhook", help="register the approvals bot webhook at QB_PUBLIC_URL (production)")
    ba = sub.add_parser("bootstrap-admin")
    ba.add_argument("--email", required=True)
    ba.add_argument("--name", required=True)
    ba.add_argument("--username", required=True)
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
    if a.cmd == "telegram-webhook":
        from .integrations.telegram import TelegramBot
        if not (settings.telegram_bot_token and settings.telegram_webhook_secret):
            raise SystemExit("set QB_TELEGRAM_BOT_TOKEN and QB_TELEGRAM_WEBHOOK_SECRET first")
        if not settings.public_url.startswith("https://"):
            raise SystemExit("Telegram webhooks need an https:// QB_PUBLIC_URL; locally run: python -m workers.telegram_poll")
        TelegramBot(settings.telegram_bot_token).set_webhook(f"{settings.public_url}/v1/integrations/telegram/webhook",
                                                             settings.telegram_webhook_secret)
        print("webhook registered")
        return 0
    if a.cmd == "bootstrap-admin":
        if users.system_admin_exists():
            raise SystemExit("refused: a System Admin already exists. Use the admin Users page to add more (PRD §5 FR-AUTH-06).")
        password = os.environ.get("QB_NEW_USER_PASSWORD") or getpass.getpass("Password for the first System Admin: ")
        problem = password_problem(password, a.username, a.email.split("@")[0], a.name)
        if problem:
            raise SystemExit(problem)
        uid = users.create_user(a.username.strip().lower(), a.email.strip().lower(), a.name, hash_password(password),
                                Role.SYSTEM_ADMIN, [])
        print("created the first System Admin", uid, "- sign in and set up two-step sign-in (MFA)")
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
