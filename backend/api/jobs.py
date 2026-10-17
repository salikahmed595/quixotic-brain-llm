"""Background jobs (PRD §11 "Redis and worker queue for parsing, embedding, indexing, notifications, and retries").
A job row records progress for the admin pages; the queue carries only its id."""
from __future__ import annotations

from typing import Optional
from uuid import UUID


def enqueue(svc, job_type: str, payload: dict, actor: Optional[UUID]) -> UUID:
    job_id = svc.ops.create_job(job_type, payload, actor)
    svc.queue.send(job_id, job_type)
    return job_id
