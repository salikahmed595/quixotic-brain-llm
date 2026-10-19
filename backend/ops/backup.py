"""Backups and a tested restore — PRD §10 (encryption at rest for backups), §11 (backups), §16 (g) "backups and restore have been tested".

    python -m backend.ops.backup create --dir /backups [--s3]        database dump + vault archive + manifest (checksums, row counts,
                                                                     audit-chain tip as an outside anchor); optional upload to S3
    python -m backend.ops.backup drill --dir /backups                restores the NEWEST backup into a throw-away database, checks
                                                                     the checksums, row counts and the audit chain, then drops it
    python -m backend.ops.backup restore --file <dump> --yes-replace-the-database     the real recovery (stop api + worker first)

Needs `pg_dump` / `pg_restore` (in the production image). Implementation choices (docs/PRD_GAPS.md §4): PostgreSQL custom-format
dumps, tar.gz of the vault, SHA-256 manifest; S3 objects use server-side encryption (AES256); keep-time set by the bucket lifecycle."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg

TABLES = ("users", "departments", "knowledge_items", "knowledge_versions", "chunks", "knowledge_proposals", "approval_decisions",
          "knowledge_gaps", "conversations", "conversation_messages", "audit_logs", "query_log", "feedback", "api_keys")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _counts(url: str) -> dict:
    with psycopg.connect(url) as c:
        out = {}
        for t in TABLES:
            try:
                out[t] = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            except psycopg.Error:
                c.rollback()
                out[t] = None
        tip = c.execute("SELECT hash FROM audit_logs a WHERE hash IS NOT NULL AND NOT EXISTS "
                        "(SELECT 1 FROM audit_logs b WHERE b.prev_hash = a.hash) ORDER BY id DESC LIMIT 1").fetchone()
    return {"rows": out, "audit_tip": tip[0] if tip else None}


def _with_db(url: str, name: str) -> str:
    u = urlparse(url)
    return urlunparse(u._replace(path="/" + name))


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"{cmd[0]} failed: {r.stderr.strip()[:500]}")


def _pg_restore(dump: Path, target_url: str, clean: bool = False) -> None:
    """pg_restore through a SQL script, run with psql (stop on the first error). A newer client (e.g. 17 in the image) writes
    `SET transaction_timeout`, which an older server (16) rejects; only that compatibility line is removed."""
    script = dump.with_suffix(".restore.sql")
    _run(["pg_restore", "--no-owner", *(["--clean", "--if-exists"] if clean else []), "--file", str(script), str(dump)])
    text = script.read_text(encoding="utf-8")
    script.write_text("\n".join(l for l in text.split("\n") if not l.startswith("SET transaction_timeout")), encoding="utf-8")
    try:
        _run(["psql", "--quiet", "-v", "ON_ERROR_STOP=1", "--single-transaction", "--file", str(script), target_url])
    finally:
        script.unlink(missing_ok=True)


def create(settings, out_dir: Path, to_s3: bool) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dump = out_dir / f"quixotic-{stamp}.dump"
    _run(["pg_dump", "--format=custom", "--no-owner", "--file", str(dump), settings.database_url])
    vault = out_dir / f"quixotic-{stamp}-vault.tar.gz"
    with tarfile.open(vault, "w:gz") as tar:
        for p in {Path(settings.vault_dir), Path(settings.vault_remote) if settings.vault_remote else None} - {None}:
            if p.exists():
                tar.add(p, arcname=p.name)
    state = _counts(settings.database_url)
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "database": dump.name, "database_sha256": _sha256(dump),
                "vault": vault.name, "vault_sha256": _sha256(vault), **state}
    mpath = out_dir / f"quixotic-{stamp}.json"
    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if to_s3:
        import boto3
        s3 = boto3.client("s3", region_name=settings.aws_region, endpoint_url=settings.s3_endpoint_url)
        for f in (dump, vault, mpath):
            s3.upload_file(str(f), settings.s3_bucket, f"backups/{f.name}", ExtraArgs={"ServerSideEncryption": "AES256"})
    _record(settings, "last_backup", {"at": manifest["created_at"], "status": "ok", "file": dump.name, "s3": to_s3,
                                      "audit_tip": manifest["audit_tip"]})
    return manifest


def drill(settings, out_dir: Path) -> dict:
    """Restore the newest backup into a temporary database and prove it is complete (§16 g)."""
    manifests = sorted(out_dir.glob("quixotic-*.json"))
    if not manifests:
        raise SystemExit(f"no backup manifest in {out_dir}")
    m = json.loads(manifests[-1].read_text(encoding="utf-8"))
    problems = []
    for key in ("database", "vault"):
        if _sha256(out_dir / m[key]) != m[f"{key}_sha256"]:
            problems.append(f"{key} file checksum does not match")
    name = "restore_drill_" + uuid.uuid4().hex[:8]
    admin_url = settings.database_url
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    target = _with_db(admin_url, name)
    try:
        _pg_restore(out_dir / m["database"], target)
        restored = _counts(target)
        for table, n in m["rows"].items():
            if restored["rows"].get(table) != n:
                problems.append(f"{table}: {restored['rows'].get(table)} rows restored, backup had {n}")
        if restored["audit_tip"] != m["audit_tip"]:
            problems.append("audit chain tip differs")
        with psycopg.connect(target) as c:
            bad = c.execute("SELECT count(*) FROM audit_logs WHERE hash IS DISTINCT FROM "
                            "audit_row_hash(prev_hash, tenant_id, at, actor_id, actor_label, event, detail)").fetchone()[0]
        if bad:
            problems.append(f"{bad} audit entries fail their hash after restore")
        with tarfile.open(out_dir / m["vault"]) as tar:
            if not tar.getmembers():
                problems.append("vault archive is empty")
    finally:
        with psycopg.connect(admin_url, autocommit=True) as c:
            c.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    result = {"backup": m["database"], "created_at": m["created_at"], "ok": not problems, "problems": problems,
              "at": datetime.now(timezone.utc).isoformat()}
    _record(settings, "last_restore_drill", result)
    return result


def restore(settings, dump: Path) -> None:
    _pg_restore(dump, settings.database_url, clean=True)


def _record(settings, key: str, value: dict) -> None:
    from ..database.accounts import SystemSettingsStore
    from ..database.pool import make_pool
    pool = make_pool(settings.database_url)
    try:
        SystemSettingsStore(pool, settings.tenant_id).set(key, value, None)
    finally:
        pool.close()


def main() -> int:
    from ..config import get_settings
    ap = argparse.ArgumentParser(prog="backend.ops.backup")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("--dir", required=True); c.add_argument("--s3", action="store_true")
    d = sub.add_parser("drill"); d.add_argument("--dir", required=True)
    r = sub.add_parser("restore"); r.add_argument("--file", required=True); r.add_argument("--yes-replace-the-database", action="store_true")
    a = ap.parse_args()
    s = get_settings()
    if a.cmd == "create":
        print(json.dumps(create(s, Path(a.dir), a.s3), indent=2))
    elif a.cmd == "drill":
        res = drill(s, Path(a.dir))
        print(json.dumps(res, indent=2))
        return 0 if res["ok"] else 1
    else:
        if not a.yes_replace_the_database:
            raise SystemExit("this replaces the live database: stop api + worker, then add --yes-replace-the-database")
        restore(s, Path(a.file))
        print("restored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
