"""Micro-batching for the CPU models — PRD §2 targets under the AT-09 load profile (40 concurrent chats, 160-chat burst).

On CPU the embedder and the reranker are far cheaper per item in one batch than one call per request: concurrent requests that
arrive within a few milliseconds share one model call. Results are identical to separate calls; only throughput changes.
Window and batch size are implementation tuning, not product decisions (docs/PRD_GAPS.md §4)."""
from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import Future
from typing import Callable, Sequence

MAX_WAIT_SECONDS = 0.01      # how long the first request waits for others to join its batch
MAX_BATCH_ITEMS = 64         # items (texts or pairs) per model call


class MicroBatcher:
    def __init__(self, fn: Callable[[list], list], max_batch: int = MAX_BATCH_ITEMS, max_wait: float = MAX_WAIT_SECONDS,
                 name: str = "batcher") -> None:
        self._fn, self._max, self._wait = fn, max_batch, max_wait
        self._q: "queue.Queue[tuple[list, Future]]" = queue.Queue()
        threading.Thread(target=self._loop, daemon=True, name=name).start()

    def submit(self, items: Sequence) -> list:
        """One caller's items in, that caller's results out (same order)."""
        if not items:
            return []
        fut: Future = Future()
        self._q.put((list(items), fut))
        return fut.result()

    def _loop(self) -> None:
        while True:
            first = self._q.get()
            batch, n = [first], len(first[0])
            deadline = time.monotonic() + self._wait
            while n < self._max:
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                try:
                    nxt = self._q.get(timeout=left)
                except queue.Empty:
                    break
                batch.append(nxt)
                n += len(nxt[0])
            flat = [x for items, _ in batch for x in items]
            try:
                out = self._fn(flat)
            except Exception as e:                       # every caller in this batch gets the error
                for _, fut in batch:
                    fut.set_exception(e)
                continue
            i = 0
            for items, fut in batch:
                fut.set_result(out[i:i + len(items)])
                i += len(items)
