"""The versioned Markdown vault — PRD §8 ("approved Obsidian-compatible Markdown files ... synchronized on the server with
version history ... Use Git"), §11 ("Versioned Markdown vault").

The vault is a Git repository on the server (`QB_VAULT_DIR`). Only the backend writes its `main` branch, and only when a proposal is
published, so every commit is an approved change with the approver in the message (§8 reversible change record). Folders follow
the §8 suggested hierarchy: the first department's name, " - " becoming a sub-folder ("Sales - Fresh Seller" -> Sales/Fresh-Seller);
archived notes move to Archive/. Front-matter keys are listed in docs/PRD_GAPS.md (the PRD names none).

IMPLEMENTATION NECESSITY: the `git` command-line tool must be installed on the server (docs/PRD_GAPS.md §4)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional

import yaml

FRONT_MATTER_KEYS = ("id", "title", "category", "departments", "sensitivity", "owner", "approved_by", "source", "effective_date",
                     "expires", "version", "status", "checksum", "updated")
_lock = threading.Lock()


class VaultError(RuntimeError):
    pass


def _slug(text: str, limit: int = 60) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return (s[:limit].rstrip("-") or "untitled")


def folder_for(department_names: list[str]) -> str:
    if not department_names:
        return "Company"
    first = sorted(department_names)[0]
    return "/".join(_slug(part, 40) for part in first.split(" - "))


def note_path(item_id: str, title: str, department_names: list[str]) -> str:
    return f"{folder_for(department_names)}/{_slug(title)}--{str(item_id)[:8]}.md"


def render_note(meta: dict, body: str) -> str:
    fm = {k: meta[k] for k in FRONT_MATTER_KEYS if meta.get(k) not in (None, "", [])}
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False) + "---\n\n" + (body or "").strip() + "\n"


def parse_note(text: str) -> tuple[dict, str]:
    """(front matter, body) of an Obsidian note. Notes without front matter give ({}, text)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, flags=re.S)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    return (fm if isinstance(fm, dict) else {}), m.group(2)


class GitVault:
    """`remote`: optional bare repository shared with the CEO's Obsidian (docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md H4). The backend
    pushes `main` there after every publication; people push only `proposals/<name>` branches (enforced by the server hook)."""

    def __init__(self, root: str, author: str = "Quixotic AI <vault@quixotic.ai>", remote: Optional[str] = None) -> None:
        self.root = Path(root).resolve()
        self.author = author
        self.remote = remote

    def _git(self, *args: str, cwd: Optional[Path] = None) -> str:
        env = {**os.environ, "QUIXOTIC_BACKEND": "1"}                 # the server hook lets only the backend write `main`
        try:
            r = subprocess.run(["git", *args], cwd=cwd or self.root, capture_output=True, text=True, timeout=120, env=env)
        except FileNotFoundError:
            raise VaultError("the git command is not installed on this server (needed for the knowledge vault, PRD §8)")
        if r.returncode != 0:
            raise VaultError(f"git {args[0]} failed: {r.stderr.strip()[:300]}")
        return r.stdout.strip()

    def ensure(self) -> None:
        if (self.root / ".git").is_dir():
            return
        name, email = re.match(r"(.*) <(.*)>", self.author).groups()
        if self.remote and self._remote_has_main():
            self.root.parent.mkdir(parents=True, exist_ok=True)
            self._git("clone", "--branch", "main", self.remote, str(self.root), cwd=self.root.parent)
            self._git("config", "user.name", name)
            self._git("config", "user.email", email)
            return
        self.root.mkdir(parents=True, exist_ok=True)
        self._git("init", "-b", "main")
        self._git("config", "user.name", name)
        self._git("config", "user.email", email)
        if self.remote:
            self._git("remote", "add", "origin", self.remote)
        (self.root / "README.md").write_text("# Quixotic AI knowledge vault\n\nApproved company knowledge. Written by the Quixotic AI "
                                             "backend when a proposal is published; do not edit `main` by hand.\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git("commit", "-m", "Create the knowledge vault")
        self._push()

    def _remote_has_main(self) -> bool:
        try:
            return bool(self._git("ls-remote", "--heads", self.remote, "main", cwd=Path.cwd()))
        except VaultError:
            return False

    def _push(self) -> None:
        if self.remote:
            self._git("push", "origin", "main")

    def _commit(self, message: str) -> str:
        if not self._git("status", "--porcelain"):
            return self._git("rev-parse", "HEAD")                 # nothing changed (e.g. metadata-only, same text)
        self._git("commit", "-m", message)
        self._push()
        return self._git("rev-parse", "HEAD")

    # ---- proposals branches (Obsidian sync) ----
    def fetch(self) -> None:
        self.ensure()
        if self.remote:
            self._git("fetch", "--prune", "origin")

    def branch_changes(self, branch: str) -> list[tuple[str, str]]:
        """(status, path) of notes changed on origin/<branch> since it split from main: A added, M modified, D deleted."""
        out = self._git("diff", "--name-status", "--no-renames", f"main...origin/{branch}")
        rows = []
        for line in out.splitlines():
            st, _, path = line.partition("\t")
            if path.lower().endswith(".md") and not path.startswith((".obsidian/", "Archive/")) and path != "README.md":
                rows.append((st[:1], path))
        return rows

    def show(self, ref: str, path: str) -> Optional[str]:
        try:
            return self._git("show", f"{ref}:{path}")
        except VaultError:
            return None

    def merge_main_into(self, branch: str) -> None:
        """After decisions, the person's branch receives the official notes (main wins where both changed), so their Obsidian shows
        what is live on the next pull. Their own unpublished notes stay on their branch."""
        if not self.remote:
            return
        with _lock:
            self.fetch()
            tmp = self.root / ".sync-worktree"
            if tmp.exists():
                self._git("worktree", "remove", "--force", str(tmp))
                shutil.rmtree(tmp, ignore_errors=True)
            self._git("worktree", "add", "--force", "-B", "sync-branch", str(tmp), f"origin/{branch}")
            try:
                self._git("merge", "-X", "theirs", "--no-edit", "main", cwd=tmp)
                self._git("push", "origin", f"HEAD:refs/heads/{branch}", cwd=tmp)
            finally:
                self._git("worktree", "remove", "--force", str(tmp))

    def publish(self, path: str, old_path: Optional[str], content: str, message: str) -> str:
        """Writes (or moves and writes) one note and commits. Returns the commit id."""
        with _lock:
            self.ensure()
            target = self.root / path
            if old_path and old_path != path and (self.root / old_path).exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                self._git("mv", old_path, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            self._git("add", "--", path)
            return self._commit(message)

    def archive(self, path: Optional[str], message: str) -> tuple[Optional[str], str]:
        """Moves a note to Archive/ and commits. Returns (new path, commit id)."""
        with _lock:
            self.ensure()
            if not path or not (self.root / path).exists():
                return path, self._git("rev-parse", "HEAD")
            new = "Archive/" + path if not path.startswith("Archive/") else path
            (self.root / new).parent.mkdir(parents=True, exist_ok=True)
            self._git("mv", path, new)
            return new, self._commit(message)

    def read(self, path: str) -> Optional[str]:
        p = self.root / path
        return p.read_text(encoding="utf-8") if p.is_file() else None

    def head(self) -> Optional[str]:
        try:
            return self._git("rev-parse", "HEAD")
        except VaultError:
            return None
