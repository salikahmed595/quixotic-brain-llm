"""Background worker (PRD §11 "Redis and worker queue for parsing, embedding, indexing, notifications, and retries"):
consumes the Redis queue (EC2) or Amazon SQS.

Job types: knowledge.process (parse + index a version, PRD §7 Documents), knowledge.publish (§8 controlled publication),
knowledge.approve_after_index (approved Obsidian import), discord.import (sales chat import), reindex (all versions).
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
    if job_type in ("knowledge.process", "document.process", "knowledge.index"):
        from backend.knowledge.service import KnowledgeService
        svc.ingestion.process_version(UUID(payload["version_id"]))
        KnowledgeService(svc).after_indexing(UUID(payload["version_id"]))
    elif job_type == "knowledge.publish":
        from backend.knowledge.service import KnowledgeService
        KnowledgeService(svc).publish(UUID(payload["proposal_id"]), payload.get("approved_by"))
    elif job_type == "knowledge.approve_after_index":
        from backend.knowledge.service import KnowledgeService
        ks = KnowledgeService(svc)
        prop = svc.knowledge.get_proposal(UUID(payload["proposal_id"]))
        if prop and prop["indexed_checksum"] != prop["checksum"]:
            svc.ingestion.process_version(prop["version_id"])
        user = svc.users.get(UUID(payload["user_id"]))
        if prop and user and user["account_status"] == "active":
            ks.decide(svc.users.principal(user), prop["id"], "approve", "approved at Obsidian import")   # queues publication when complete
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
    if hasattr(services.queue, "requeue_stale"):
        n = services.queue.requeue_stale()                  # jobs a stopped worker left half-done go back to the queue
        if n:
            log.info("requeued %s unfinished job(s)", n)
    while True:
        run_once(services)
