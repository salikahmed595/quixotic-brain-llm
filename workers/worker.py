"""Background worker (PRD §47): consumes Amazon SQS messages, runs on ECS.

Job types: document.process, knowledge.index (§13.3), discord.import (§17.2), reindex (§24.2).
Progress is written to the `jobs` table so the frontend can show it (§47).
Run: python -m workers.worker
"""
from __future__ import annotations

import logging
from uuid import UUID

from backend.api.services import Services, build_services
from backend.config import get_settings

log = logging.getLogger("worker")


def handle(svc: Services, job_type: str, job: dict) -> None:
    payload = job["payload"]
    if job_type in ("document.process", "knowledge.index"):
        svc.ingestion.process_version(UUID(payload["version_id"]))
    elif job_type == "discord.import":
        raw = svc.storage.get(payload["s3_key"])
        svc.importer.run(raw, UUID(payload["department_id"]), job["id"],
                         on_progress=lambda done, total: svc.ops.update_job(job["id"], done=done, total=total))
    elif job_type == "reindex":
        ids = svc.knowledge.all_version_ids_with_content()
        svc.ops.update_job(job["id"], done=0, total=len(ids))
        for n, vid in enumerate(ids, 1):
            svc.ingestion.process_version(vid)
            svc.ops.update_job(job["id"], done=n)
    else:
        raise ValueError(f"unknown job type {job_type!r}")


def run_once(svc: Services, wait_seconds: int = 20) -> bool:
    msg = svc.queue.receive(wait_seconds)
    if msg is None:
        return False
    body, receipt = msg
    job_id = UUID(body["job_id"])
    job = svc.ops.get_job(job_id)
    if job is None:
        svc.queue.delete(receipt)
        return True
    svc.ops.update_job(job_id, status="running")
    try:
        handle(svc, job["type"], job)
        svc.ops.update_job(job_id, status="succeeded")
    except Exception as exc:                       # surface the real reason to admins (System Health, §55 failed jobs)
        log.exception("job %s failed", job_id)
        svc.ops.update_job(job_id, status="failed", error=str(exc)[:1000])
    svc.queue.delete(receipt)
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    services = build_services(get_settings(), warm_reranker=False)
    while True:
        run_once(services)
