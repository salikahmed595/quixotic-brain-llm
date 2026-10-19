"""MicroBatcher: concurrent callers share model calls but each gets exactly its own results, in order; errors reach everyone."""
import threading
import time

import pytest

from backend.retrieval.batching import MicroBatcher


def test_concurrent_callers_share_calls_and_get_their_own_results():
    calls = []
    def fn(items):
        calls.append(len(items)); time.sleep(0.02); return [x * 10 for x in items]
    b = MicroBatcher(fn, max_batch=64, max_wait=0.05)
    out = {}
    def caller(k):
        out[k] = b.submit([k, k + 1000])
    threads = [threading.Thread(target=caller, args=(k,)) for k in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert all(out[k] == [k * 10, (k + 1000) * 10] for k in range(20))
    assert sum(calls) == 40 and len(calls) < 20                               # fewer model calls than callers


def test_errors_reach_every_caller_in_the_batch():
    def fn(items): raise RuntimeError("model crashed")
    b = MicroBatcher(fn, max_wait=0.01)
    with pytest.raises(RuntimeError):
        b.submit(["x"])
    assert b.submit([]) == []
