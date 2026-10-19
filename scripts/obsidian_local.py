"""Local Obsidian Git sync for testing on one PC (no server, no SSH, no Telegram) — PRD §9 knowledge updates from Obsidian.

Mirrors deploy/vault (docs/DEPLOYMENT.md §7) with a local bare repository instead of vault@server:
    python scripts/obsidian_local.py setup --email ceo@company.com --name ceo
      - creates .obsidian-remote.git (the "server" repository) with local hooks, and connects the backend vault to it
      - sets QB_VAULT_REMOTE and (if missing) QB_HERMES_SHARED_SECRET in .env   -> restart the app afterwards
      - links the Obsidian branch `ceo` to that user (same as System -> Integrations)
      - clones obsidian-vault/ on branch proposals/ceo: open that folder as a vault in Obsidian
    Then write a note in obsidian-vault/, commit and push (Obsidian Git plugin or `git push`): it becomes a proposal in Approvals.
    python scripts/obsidian_local.py notify <branch> <commit>     (called by the post-receive hook)"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE, CLONE, ENV = ROOT / ".obsidian-remote.git", ROOT / "obsidian-vault", ROOT / ".env"


def env_values() -> dict:
    out = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def set_env(key: str, value: str) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines()
    lines = [l for l in lines if not l.startswith(f"{key}=")] + [f"{key}={value}"]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def git(*args: str, cwd: Path = ROOT) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env={**os.environ, "QUIXOTIC_BACKEND": "1"})
    if r.returncode:
        raise SystemExit(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


PRE_RECEIVE = """#!/bin/sh
# Local copy of deploy/vault/pre-receive: people may push only proposals/<name>; no deleting, no force-push.
zero=0000000000000000000000000000000000000000
while read old new ref; do
  [ "$QUIXOTIC_BACKEND" = "1" ] && continue
  case "$ref" in refs/heads/proposals/*) ;; *) echo "Quixotic AI: push to your proposals/<name> branch only" >&2; exit 1 ;; esac
  [ "$new" = "$zero" ] && { echo "Quixotic AI: deleting your proposals branch is not allowed" >&2; exit 1; }
  if [ "$old" != "$zero" ] && ! git merge-base --is-ancestor "$old" "$new"; then
    echo "Quixotic AI: force-push is not allowed; pull first" >&2; exit 1
  fi
done
"""

POST_RECEIVE = """#!/bin/sh
[ "$QUIXOTIC_BACKEND" = "1" ] && exit 0
while read old new ref; do
  case "$ref" in refs/heads/proposals/*) "{python}" "{script}" notify "${{ref#refs/heads/}}" "$new" ;; esac
done
"""


def setup(email: str, name: str) -> None:
    vault_dir = Path(env_values().get("QB_VAULT_DIR", ".devvault"))
    vault_dir = vault_dir if vault_dir.is_absolute() else ROOT / vault_dir
    if not (vault_dir / ".git").is_dir():
        raise SystemExit(f"{vault_dir} is not a Git vault yet: start the app once first")
    if not REMOTE.exists():
        git("init", "--bare", "-b", "main", str(REMOTE))
    hooks = REMOTE / "hooks"
    (hooks / "pre-receive").write_text(PRE_RECEIVE, encoding="utf-8", newline="\n")
    (hooks / "post-receive").write_text(POST_RECEIVE.format(python=Path(sys.executable).as_posix(),
                                                            script=Path(__file__).resolve().as_posix()), encoding="utf-8", newline="\n")
    remotes = git("remote", cwd=vault_dir).split()
    git("remote", "set-url" if "origin" in remotes else "add", "origin", REMOTE.as_posix(), cwd=vault_dir)
    git("push", "origin", "main", cwd=vault_dir)                                # publish the approved knowledge to the "server"
    set_env("QB_VAULT_REMOTE", REMOTE.as_posix())
    if len(env_values().get("QB_HERMES_SHARED_SECRET", "")) < 32:
        set_env("QB_HERMES_SHARED_SECRET", secrets.token_urlsafe(48))         # signs hook -> API calls; never printed

    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("QB_DATABASE_URL", env_values()["QB_DATABASE_URL"])
    from backend.config import get_settings
    from backend.database.integrations import IntegrationStore
    from backend.database.pool import make_pool
    from backend.database.users import UserStore
    s = get_settings()
    pool = make_pool(s.database_url)
    user = UserStore(pool, s.tenant_id).get_by_login(email)
    if not user:
        raise SystemExit(f"no account {email!r}")
    store = IntegrationStore(pool, s.tenant_id)
    if not store.user_for("obsidian", name):
        store.add_identity("obsidian", name, user["id"], f"local test ({email})", None)

    if not CLONE.exists():
        git("clone", "--branch", "main", REMOTE.as_posix(), str(CLONE))
        git("checkout", "-b", f"proposals/{name}", cwd=CLONE)
        git("push", "-u", "origin", f"proposals/{name}", cwd=CLONE)
    print(f"Ready. Restart the app, then open {CLONE} as a vault in Obsidian (branch proposals/{name}).")


def notify(branch: str, commit: str) -> None:
    e = env_values()
    body = json.dumps({"branch": branch, "commit": commit}).encode()
    ts = str(int(time.time()))
    sig = hmac.new(e["QB_HERMES_SHARED_SECRET"].encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(e.get("QB_PUBLIC_URL", "http://localhost:8000").rstrip("/") + "/v1/integrations/vault/push", data=body,
                                 headers={"Content-Type": "application/json", "X-Quixotic-Timestamp": ts, "X-Quixotic-Signature": sig})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read() or b"{}")
    except Exception as exc:
        print(f"Quixotic AI: could not reach the app ({exc}); your notes are saved. Push again later.")
        return
    for r in res.get("results", []):
        print(f"Quixotic AI: {r.get('note')}: " + (f"sent for review ({r.get('kind')})" if r.get("proposal") else r.get("error") or r.get("skipped", "")))
    if res.get("ignored"):
        print(f"Quixotic AI: {res['ignored']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="obsidian_local")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup"); s.add_argument("--email", required=True); s.add_argument("--name", default="ceo")
    n = sub.add_parser("notify"); n.add_argument("branch"); n.add_argument("commit")
    a = ap.parse_args()
    setup(a.email, a.name) if a.cmd == "setup" else notify(a.branch, a.commit)
