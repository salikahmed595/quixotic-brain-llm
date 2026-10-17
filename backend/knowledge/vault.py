"""The versioned Markdown vault — PRD §8 ("approved Obsidian-compatible Markdown files ... synchronized on the server with
version history ... Use Git"), §11 ("Versioned Markdown vault").

The vault is a Git repository on the server (`QB_VAULT_DIR`). Only the backend writes its `main` branch, and only when a proposal is
published, so every commit is an approved change with the approver in the message (§8 reversible change record). Folders follow
the §8 suggested hierarchy: the first department's name, " - " becoming a sub-folder ("Sales - Fresh Seller" -> Sales/Fresh-Seller);
archived notes move to Archive/. Front-matter keys are listed in docs/PRD_GAPS.md (the PRD names none).

IMPLEMENTATION NECESSITY: the `git` command-line tool must be installed on the server (docs/PRD_GAPS.md §4)."""
from __future__ import annotations

import re
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
    def __init__(self, root: str, author: str = "Quixotic AI <vault@quixotic.ai>") -> None:
        self.root = Path(root).resolve()
        self.author = author

    def _git(self, *args: str) -> str:
        try:
            r = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            raise VaultError("the git command is not installed on this server (needed for the knowledge vault, PRD §8)")
        if r.returncode != 0:
            raise VaultError(f"git {args[0]} failed: {r.stderr.strip()[:300]}")
        return r.stdout.strip()

    def ensure(self) -> None:
        if (self.root / ".git").is_dir():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        self._git("init", "-b", "main")
        name, email = re.match(r"(.*) <(.*)>", self.author).groups()
        self._git("config", "user.name", name)
        self._git("config", "user.email", email)
        (self.root / "README.md").write_text("# Quixotic AI knowledge vault\n\nApproved company knowledge. Written by the Quixotic AI "
                                             "backend when a proposal is published; do not edit `main` by hand.\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git("commit", "-m", "Create the knowledge vault")

    def _commit(self, message: str) -> str:
        if not self._git("status", "--porcelain"):
            return self._git("rev-parse", "HEAD")                 # nothing changed (e.g. metadata-only, same text)
        self._git("commit", "-m", message)
        return self._git("rev-parse", "HEAD")

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
            self._git("add", path)
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
