"""Amazon S3 raw storage (PRD §46) and Amazon SQS job queue (PRD §47). Buckets must be private (§51)."""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

from ..config import Settings


# A job (e.g. embedding a long PDF on CPU) can outlast SQS's 30 s default; without this another worker would pick the same
# message up mid-processing. Implementation necessity (docs/PRD_GAPS.md).
VISIBILITY_TIMEOUT_SECONDS = 900


def raw_document_key(file_id: UUID, filename: str) -> str:
    return f"raw/documents/{file_id}/{filename}"            # §46 /raw/documents/


def raw_discord_key(job_id: UUID, filename: str) -> str:
    return f"raw/discord/{job_id}/{filename}"                # §46 /raw/discord/


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        import boto3
        self._bucket = settings.s3_bucket
        self._s3 = boto3.client("s3", region_name=settings.aws_region, endpoint_url=settings.s3_endpoint_url)

    def put(self, key: str, data: bytes) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=data)

    def get(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)


class LocalDirStorage:
    """Local development stand-in for S3: the in-memory S3 emulator forgets every upload when it restarts, which lost real
    documents. Same keys as S3 (§46), stored under a folder. Never used in production (docs/PRD_GAPS.md)."""
    def __init__(self, root: str) -> None:
        from pathlib import Path
        self._root = Path(root).resolve()

    def _path(self, key: str):
        path = (self._root / key).resolve()
        if self._root not in path.parents:
            raise ValueError("bad storage key")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class SQSQueue:
    def __init__(self, settings: Settings) -> None:
        import boto3
        self._url = settings.sqs_queue_url
        self._sqs = boto3.client("sqs", region_name=settings.aws_region, endpoint_url=settings.sqs_endpoint_url)

    def send(self, job_id: UUID, job_type: str) -> None:
        self._sqs.send_message(QueueUrl=self._url, MessageBody=json.dumps({"job_id": str(job_id), "type": job_type}))

    def receive(self, wait_seconds: int = 20) -> Optional[tuple[dict, str]]:
        r = self._sqs.receive_message(QueueUrl=self._url, MaxNumberOfMessages=1, WaitTimeSeconds=wait_seconds,
                                       VisibilityTimeout=VISIBILITY_TIMEOUT_SECONDS)
        msgs = r.get("Messages", [])
        return (json.loads(msgs[0]["Body"]), msgs[0]["ReceiptHandle"]) if msgs else None

    def delete(self, receipt: str) -> None:
        self._sqs.delete_message(QueueUrl=self._url, ReceiptHandle=receipt)


class RedisQueue:
    """PRD §11 "Redis and worker queue" (owner: one EC2 server, Redis in a container). Reliable-queue pattern: a received job is
    moved to a processing list and removed only when the worker is done, so a worker that crashes mid-job does not lose it
    (`requeue_stale` puts such jobs back; the worker calls it on start)."""

    def __init__(self, url: str, name: str = "quixotic:jobs", client=None) -> None:
        if client is None:
            import redis
            client = redis.Redis.from_url(url, decode_responses=True)
        self._r, self._q, self._p = client, name, f"{name}:processing"

    def send(self, job_id: UUID, job_type: str) -> None:
        self._r.lpush(self._q, json.dumps({"job_id": str(job_id), "type": job_type}))

    def receive(self, wait_seconds: int = 20) -> Optional[tuple[dict, str]]:
        raw = (self._r.lmove(self._q, self._p, "RIGHT", "LEFT") if wait_seconds <= 0
               else self._r.blmove(self._q, self._p, wait_seconds, "RIGHT", "LEFT"))
        return (json.loads(raw), raw) if raw else None

    def delete(self, receipt: str) -> None:
        self._r.lrem(self._p, 1, receipt)

    def requeue_stale(self) -> int:
        """On worker start: jobs left in the processing list by a stopped worker go back to the queue (single worker per server)."""
        n = 0
        while self._r.lmove(self._p, self._q, "RIGHT", "LEFT"):
            n += 1
        return n
