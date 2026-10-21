"""Local Obsidian contributors on one PC (no server, no SSH) — the same private-repository model as the server
(backend/knowledge/contributors.py, docs/DEPLOYMENT.md §6), for testing.

    python scripts/obsidian_local.py setup --contributor ceo=ceo@company.com --contributor sales=lead@company.com ...
      - sets QB_VAULT_CONTRIBUTORS_DIR (.obsidian-contributors) and, if missing, QB_VAULT_HOOK_SECRET in .env; writes the
        hooks' hooks.env (app address + secret)                                     -> restart the app after the first run
      - links each name to that account (System -> Integrations) and builds their private repository with the notes they may see
      - clones obsidian-vaults/<name>/ on branch proposals/<name> with Obsidian Git settings (auto commit-and-sync every 2 min)
    Open obsidian-vaults/<name>/ as a vault in Obsidian, install the Obsidian Git community plugin, and write notes."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRIB, VAULTS, ENV = ROOT / ".obsidian-contributors", ROOT / "obsidian-vaults", ROOT / ".env"

# Obsidian Git plugin settings (data.json; the plugin fills in defaults for anything not listed): commit-and-sync every
# 2 minutes, pull every 5 minutes and when Obsidian opens, always pull before pushing, merge (never rebase/force).
OBSIDIAN_GIT = {"autoSaveInterval": 2, "autoPullInterval": 5, "autoPullOnBoot": True, "pullBeforePush": True,
                "syncMethod": "merge", "disablePush": False, "commitMessage": "Notes: {{date}}",
                "autoCommitMessage": "Notes: {{date}}", "disablePopups": False}


def env_values() -> dict:
    out = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def set_env(key: str, value: str | None) -> None:
    lines = [l for l in ENV.read_text(encoding="utf-8").splitlines() if not l.startswith(f"{key}=")]
    if value is not None:
        lines.append(f"{key}={value}")
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def git(*args: str, cwd: Path = ROOT) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def setup(pairs: list[str]) -> None:
    set_env("QB_VAULT_CONTRIBUTORS_DIR", CONTRIB.as_posix())
    set_env("QB_VAULT_REMOTE", None)                      # the old single shared repository handed everyone every note
    if len(env_values().get("QB_VAULT_HOOK_SECRET", "")) < 32:
        set_env("QB_VAULT_HOOK_SECRET", secrets.token_urlsafe(48))
    e = env_values()
    CONTRIB.mkdir(exist_ok=True)
    (CONTRIB / "hooks.env").write_text(f"QUIXOTIC_API_URL={e.get('QB_PUBLIC_URL', 'http://localhost:8000')}\n"
                                       f"QB_VAULT_HOOK_SECRET={e['QB_VAULT_HOOK_SECRET']}\n", encoding="utf-8", newline="\n")
    for k in ("QB_VAULT_CONTRIBUTORS_DIR", "QB_VAULT_HOOK_SECRET", "QB_DATABASE_URL"):
        os.environ[k] = env_values()[k]
    os.environ.pop("QB_VAULT_REMOTE", None)
    sys.path.insert(0, str(ROOT))
    from backend.api.services import build_services
    from backend.config import get_settings
    from backend.knowledge.vault import GitVault
    from backend.knowledge.vault_sync import VaultSync
    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
    s = get_settings()
    GitVault(s.vault_dir).ensure()
    svc = build_services(s, run_migrations=False, warm_reranker=False)
    for pair in pairs:
        name, _, email = pair.partition("=")
        user = svc.users.get_by_login(email)
        if not user:
            raise SystemExit(f"no account {email!r}")
        current = svc.integrations.user_for("obsidian", name)
        if current and current["id"] != user["id"]:
            raise SystemExit(f"{name} is already linked to another account")
        if not current:
            svc.integrations.add_identity("obsidian", name, user["id"], f"local test ({email})", None)
        print(f"{name}: {VaultSync(svc).refresh_views(name)[name]}")
        clone = VAULTS / name
        if not clone.exists():
            VAULTS.mkdir(exist_ok=True)
            git("clone", "-q", (CONTRIB / f"{name}.git").as_posix(), str(clone))
            git("config", "user.name", name, cwd=clone)
            git("config", "user.email", email, cwd=clone)
            (clone / ".gitignore").write_text(".obsidian/\n.trash/\n", encoding="utf-8")
            git("checkout", "-q", "-b", f"proposals/{name}", cwd=clone)
            git("add", ".gitignore", cwd=clone)
            git("commit", "-q", "-m", "Start my notes", cwd=clone)
            git("push", "-q", "-u", "origin", f"proposals/{name}", cwd=clone)
        plug = clone / ".obsidian" / "plugins" / "obsidian-git"
        plug.mkdir(parents=True, exist_ok=True)
        (plug / "data.json").write_text(json.dumps(OBSIDIAN_GIT, indent=2), encoding="utf-8")
        print(f"  open {clone} in Obsidian (branch proposals/{name})")
    print("Restart the app if this was the first run (new .env values).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="obsidian_local")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--contributor", action="append", required=True, help="name=email, repeatable (e.g. ceo=ceo@company.com)")
    a = ap.parse_args()
    setup(a.contributor)
