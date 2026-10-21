"""One private Git repository per Obsidian contributor — PRD §3 (deny by default), §8/§10 (permission filters on every read),
§9 (knowledge updates from people's own tools, always reviewed), §15 (no employee access to unpublished or unpermitted content).

Owner request 2026-10-20 (docs/PRD_GAPS.md §0): three contributors with their own Obsidian vaults. A single shared repository
would hand every contributor every published note (all departments, every sensitivity level) and the other contributors'
branches, so each contributor gets a separate bare repository `<contributors_dir>/<name>.git`:

    main               written ONLY by this backend: the published notes this contributor may see (their account's departments
                       and sensitivity levels), refreshed after every publication and whenever their access changes
    proposals/<name>   the only branch they may push (server hooks); every changed note becomes a proposal for review

The backend's working copy of each repository lives in `<contributors_dir>/_views/<name>` (never served over SSH)."""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional

from ..permissions.access import Principal, resolve_department_scope
from .vault import GitVault, VaultError

log = logging.getLogger("contributors")
NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")

# Server hooks, installed in every contributor repository. POSIX sh + git + curl + openssl only: on the server they run as the
# `vault` user outside the containers; on Windows Git Bash ships the same tools (scripts/obsidian_local.py).
PRE_RECEIVE = """#!/bin/sh
# Quixotic AI contributor repository ({name}). Only the backend writes `main`; this person may push only proposals/{name}:
# no other branch, no deleting, no force-push (PRD §9, §15).
zero=0000000000000000000000000000000000000000
while read old new ref; do
  if [ "$QUIXOTIC_BACKEND" = "1" ] && [ -z "$SSH_CONNECTION" ]; then continue; fi
  if [ "$ref" != "refs/heads/proposals/{name}" ]; then
    echo "Quixotic AI: you may only push to proposals/{name}" >&2; exit 1
  fi
  if [ "$new" = "$zero" ]; then echo "Quixotic AI: deleting your branch is not allowed" >&2; exit 1; fi
  if [ "$old" != "$zero" ] && ! git merge-base --is-ancestor "$old" "$new"; then
    echo "Quixotic AI: force-push is not allowed; pull first" >&2; exit 1
  fi
done
"""

POST_RECEIVE = """#!/bin/sh
# Tells Quixotic AI that proposals/{name} changed; the notes become proposals for review. Signed with the vault hook secret:
# HMAC-SHA256(QB_VAULT_HOOK_SECRET, "<timestamp>.<body>"). If the app is unreachable the worker picks the push up later.
[ "$QUIXOTIC_BACKEND" = "1" ] && exit 0
env_file="$(cd "$(git rev-parse --git-dir)/.." && pwd)/hooks.env"
[ -f "$env_file" ] || {{ echo "Quixotic AI: saved; the server will pick your notes up shortly."; exit 0; }}
. "$env_file"
while read old new ref; do
  [ "$ref" = "refs/heads/proposals/{name}" ] || continue
  body=$(printf '{{"branch":"proposals/{name}","commit":"%s"}}' "$new")
  ts=$(date +%s)
  sig=$(printf '%s.%s' "$ts" "$body" | openssl dgst -sha256 -hmac "$QB_VAULT_HOOK_SECRET" | sed 's/^.* //')
  if out=$(curl -fsS -m 120 -X POST "$QUIXOTIC_API_URL/v1/integrations/vault/push" -H "Content-Type: application/json" \\
       -H "X-Quixotic-Timestamp: $ts" -H "X-Quixotic-Signature: $sig" --data "$body"); then
    echo "Quixotic AI: your notes were received: $out"
  else
    echo "Quixotic AI: saved; the app could not be reached, the server will pick your notes up shortly."
  fi
done
"""


class ContributorRepos:
    def __init__(self, root: str, master: GitVault, author: str = "Quixotic AI <vault@quixotic.ai>") -> None:
        self.root = Path(root).resolve()
        self.master = master
        self.author = author

    # ---- paths ----
    def repo(self, name: str) -> Path:
        self._check(name)
        return self.root / f"{name}.git"

    def view(self, name: str) -> Path:
        self._check(name)
        return self.root / "_views" / name

    @staticmethod
    def _check(name: str) -> None:
        if not NAME.match(name or ""):
            raise VaultError("a contributor name is lowercase letters, numbers, - or _ (e.g. ceo)")

    def _git(self, *args: str, cwd: Optional[Path] = None) -> str:
        env = {**os.environ, "QUIXOTIC_BACKEND": "1"}
        env.pop("SSH_CONNECTION", None)
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120, env=env)
        if r.returncode != 0:
            raise VaultError(f"git {args[0]} failed: {r.stderr.strip()[:300]}")
        return r.stdout.strip()

    # ---- set-up ----
    def ensure(self, name: str) -> None:
        """Create the bare repository (with hooks) and the backend's working copy. Safe to call again."""
        repo, view = self.repo(name), self.view(name)
        if not repo.exists():
            repo.parent.mkdir(parents=True, exist_ok=True)
            self._git("init", "--bare", "-b", "main", str(repo))
        hooks = repo / "hooks"
        for hook, text in (("pre-receive", PRE_RECEIVE), ("post-receive", POST_RECEIVE)):
            p = hooks / hook
            p.write_text(text.format(name=name), encoding="utf-8", newline="\n")
            p.chmod(0o755)
        if not (view / ".git").is_dir():
            view.parent.mkdir(parents=True, exist_ok=True)
            self._git("init", "-b", "main", str(view))
            n, e = re.match(r"(.*) <(.*)>", self.author).groups()
            self._git("config", "user.name", n, cwd=view)
            self._git("config", "user.email", e, cwd=view)
            self._git("remote", "add", "origin", repo.as_posix(), cwd=view)
            (view / "README.md").write_text(
                "# Quixotic AI knowledge (your view)\n\nThe approved notes you may see. Write new notes or edit these on your branch "
                f"`proposals/{name}`; every change is reviewed before it goes live.\n", encoding="utf-8")
            self._git("add", "README.md", cwd=view)
            self._git("commit", "-m", "Create your knowledge view", cwd=view)
            self._git("push", "origin", "main", cwd=view)

    # ---- the filtered view ----
    def refresh(self, name: str, visible_paths: Optional[Iterable[str]]) -> dict:
        """Write `main` = exactly the published notes in `visible_paths` (None = the account is not active: nothing), then bring
        the person's branch up to date (published text wins where both changed). Returns what changed."""
        self.ensure(name)
        view = self.view(name)
        want = {p for p in (visible_paths or []) if p and p.endswith(".md") and not p.startswith("Archive/")}
        self._git("checkout", "-q", "main", cwd=view)
        have = {p for p in self._git("ls-files", cwd=view).splitlines() if p.endswith(".md") and p != "README.md"}
        removed = sorted(have - want)
        for p in removed:
            self._git("rm", "-q", "--", p, cwd=view)
        written = 0
        for p in sorted(want):
            text = self.master.read(p)
            if text is None:
                continue
            target = view / p
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8", newline="\n")
                self._git("add", "--", p, cwd=view)
                written += 1
        changed = bool(self._git("status", "--porcelain", cwd=view))
        if changed:
            self._git("commit", "-q", "-m", f"Update your view: {written} note(s) added or changed, {len(removed)} removed", cwd=view)
            self._git("push", "-q", "origin", "main", cwd=view)
        conflict = self._merge_main_into_branch(name)
        return {"changed": changed, "written": written, "removed": len(removed), "conflict": conflict}

    def _merge_main_into_branch(self, name: str) -> Optional[str]:
        view, branch = self.view(name), f"proposals/{name}"
        self._git("fetch", "-q", "--prune", "origin", cwd=view)
        if not self._git("branch", "-r", "--list", f"origin/{branch}", cwd=view):
            return None
        tmp = self.root / "_views" / f".merge-{name}"
        if tmp.exists():
            try:
                self._git("worktree", "remove", "--force", str(tmp), cwd=view)
            except VaultError:
                pass
            shutil.rmtree(tmp, ignore_errors=True)
        self._git("worktree", "add", "-q", "--force", "-B", "merge-branch", str(tmp), f"origin/{branch}", cwd=view)
        try:
            try:
                self._git("merge", "-q", "-X", "theirs", "--no-edit", "main", cwd=tmp)
            except VaultError as e:
                # e.g. the person edited a note that has since been removed from their view: leave their branch as it is and
                # report it (activity log); they pull, resolve in Obsidian and push again.
                try:
                    self._git("merge", "--abort", cwd=tmp)
                except VaultError:
                    pass
                return str(e)
            self._git("push", "-q", "origin", f"HEAD:refs/heads/{branch}", cwd=tmp)
            return None
        finally:
            self._git("worktree", "remove", "--force", str(tmp), cwd=view)

    # ---- reading a person's pushed notes ----
    def fetch(self, name: str) -> None:
        self.ensure(name)
        self._git("fetch", "-q", "--prune", "origin", cwd=self.view(name))

    def head(self, name: str) -> Optional[str]:
        try:
            return self._git("rev-parse", f"origin/proposals/{name}", cwd=self.view(name))
        except VaultError:
            return None

    def branch_changes(self, name: str) -> list[tuple[str, str]]:
        """(status, path) of notes changed on the person's branch since it split from their `main`: A, M or D."""
        out = self._git("diff", "--name-status", "--no-renames", f"main...origin/proposals/{name}", cwd=self.view(name))
        changes = []
        for line in out.splitlines():
            status, _, path = line.partition("\t")
            if path.endswith(".md") and path != "README.md" and not path.startswith((".obsidian/", "_views/")):
                changes.append((status[0], path))
        return changes

    def show(self, name: str, ref: str, path: str) -> Optional[str]:
        try:
            return self._git("show", f"{ref}:{path}", cwd=self.view(name))
        except VaultError:
            return None


def visible_paths(svc, principal: Principal) -> list[str]:
    """The vault paths of published notes this person may see: departments (§10) AND sensitivity level (§8)."""
    allowed = resolve_department_scope(principal, svc.users.all_department_ids())
    levels = {lvl for lvl, roles in svc.settings.sensitivity_levels.items() if principal.role.value in roles}
    out = []
    for row in svc.knowledge.published_vault_files():
        if row["sensitivity"] in levels and set(row["department_ids"]) & allowed:
            out.append(row["vault_path"])
    return out
