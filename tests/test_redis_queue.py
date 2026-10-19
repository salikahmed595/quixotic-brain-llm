"""RedisQueue (PRD §11 "Redis and worker queue"): FIFO, a job stays in the processing list until done, unfinished jobs come back."""
import os
from uuid import uuid4

import pytest

from backend.ingestion.storage import RedisQueue


class MiniRedis:
    """The four list commands RedisQueue uses, with Redis semantics."""
    def __init__(self): self.lists = {}
    def _l(self, k): return self.lists.setdefault(k, [])
    def lpush(self, k, v): self._l(k).insert(0, v)
    def lmove(self, src, dst, wherefrom, whereto):
        s = self._l(src)
        if not s: return None
        v = s.pop() if wherefrom == "RIGHT" else s.pop(0)
        (self._l(dst).insert(0, v) if whereto == "LEFT" else self._l(dst).append(v))
        return v
    def blmove(self, src, dst, timeout, wherefrom, whereto): return self.lmove(src, dst, wherefrom, whereto)
    def lrem(self, k, n, v):
        if v in self._l(k): self._l(k).remove(v)


def _exercise(q):
    a, b = uuid4(), uuid4()
    q.send(a, "knowledge.process"); q.send(b, "knowledge.publish")
    body, receipt = q.receive(0)
    assert body == {"job_id": str(a), "type": "knowledge.process"}           # first in, first out
    assert q.requeue_stale() == 1                                             # a worker died holding `a`: it comes back
    first = q.receive(0); q.delete(first[1])
    second = q.receive(0); q.delete(second[1])
    assert {first[0]["job_id"], second[0]["job_id"]} == {str(a), str(b)} and q.receive(0) is None


def test_redis_queue_semantics():
    _exercise(RedisQueue("redis://unused", name=f"t:{uuid4()}", client=MiniRedis()))


@pytest.mark.skipif(not os.environ.get("QB_TEST_REDIS_URL"), reason="needs a real Redis (QB_TEST_REDIS_URL)")
def test_redis_queue_on_a_real_redis():
    _exercise(RedisQueue(os.environ["QB_TEST_REDIS_URL"], name=f"t:{uuid4()}"))


def test_blocking_wait_fits_inside_socket_timeout():
    """QA 2026-10-19: redis-py 8 defaults to a 5 s read timeout, so a 20 s BLMOVE on an idle queue killed the worker."""
    q = RedisQueue("redis://localhost:1/0")
    timeout = q._r.connection_pool.connection_kwargs["socket_timeout"]
    calls = []
    q._r.blmove = lambda src, dst, wait, a, b: calls.append(wait)
    q.receive(600)
    assert calls[0] < timeout
