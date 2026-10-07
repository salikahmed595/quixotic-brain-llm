"""Retrieval metrics named in PRD §59: Recall@5, Recall@10, MRR."""
from __future__ import annotations

from typing import Sequence


def rank_of(expected: str, ranked_sources: Sequence[str]) -> int | None:
    """1-based rank of the first result whose source title equals `expected` (case-insensitive)."""
    for i, s in enumerate(ranked_sources, 1):
        if s.strip().lower() == expected.strip().lower():
            return i
    return None


def recall_at(ranks: Sequence[int | None], k: int) -> float:
    return sum(r is not None and r <= k for r in ranks) / len(ranks) if ranks else 0.0


def mrr(ranks: Sequence[int | None]) -> float:
    return sum(1 / r for r in ranks if r) / len(ranks) if ranks else 0.0
