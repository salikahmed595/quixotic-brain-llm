"""Learning from 👍 / 👎 — owner request; PRD §21 (feedback is stored) and Phase 5 ("feedback-based improvements").

What it does, and the limits that keep it inside the PRD non-goals (§5: no automatic fine-tuning, no autonomous changes to company data):
  1. chunk_boost / reorder : a passage whose answers were often rated helpful moves up a little in the retrieval ORDER, one that was often
                             rated not helpful moves down a little. Bounded, needs MIN_VOTES, never edits or hides knowledge.
  2. style_hints           : patterns in one person's own ratings (short vs detailed, lists vs paragraphs) become style hints for the model.
Every number below is a placeholder chosen to be mild; none comes from the PRD (docs/PRD_GAPS.md).
"""
from __future__ import annotations

import re
import statistics
from typing import Sequence

MIN_VOTES = 3            # fewer ratings than this on a passage: no effect at all
SHRINK = 5               # pulls small samples toward 0: 3 up / 0 down gives +0.375, not +1
WEIGHT = 0.001           # 3 ratings move a passage ~1 place; even a near-unanimous history moves it at most ~4 places (adjacent RRF ranks differ by ~0.0003)
TOP_POSITIONS = 2        # a rating is credited to the first two passages of the answer only (the ones the answer most likely used)
RRF_K = 60


def chunk_boost(up: int, down: int) -> float:
    """-1..1, 0 until MIN_VOTES ratings exist."""
    n = up + down
    return 0.0 if n < MIN_VOTES else (up - down) / (n + SHRINK)


def make_signal_source(ops, settings):
    """callable(chunk_ids) -> {chunk_id: boost}, handed to SearchService. Off when `settings.feedback_learning` is false."""
    def signals(chunk_ids):
        if not settings.feedback_learning:
            return {}
        votes = ops.chunk_votes(chunk_ids, TOP_POSITIONS, ops.learning_since())
        return {cid: chunk_boost(up, down) for cid, (up, down) in votes.items()}
    return signals


def reorder(candidates: list, boosts: dict) -> list:
    """Retrieval order nudged by learned boosts. Without any boost the order is returned unchanged."""
    if not boosts or not any(boosts.get(c.chunk_id) for c in candidates):
        return candidates
    scored = [(1 / (RRF_K + i) + WEIGHT * boosts.get(c.chunk_id, 0.0), -i, c) for i, c in enumerate(candidates, 1)]
    return [c for _, _, c in sorted(scored, key=lambda t: (t[0], t[1]), reverse=True)]


_LIST_LINE = re.compile(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)")
REASON_TOO_LONG, REASON_TOO_SHORT = "too long", "too short"


def _words(text: str) -> int:
    return len((text or "").split())


def _has_list(text: str) -> bool:
    return any(_LIST_LINE.match(line) for line in (text or "").splitlines())


def style_hints(rows: Sequence[dict]) -> list[str]:
    """`rows`: one per rated answer of ONE person: {helpful: bool, answer: str, reasons: [str]}.
    Returns short English hints such as "short, to-the-point answers". Needs both liked and disliked examples to find a CONTRAST;
    a person who only ever clicks 👍 gets no invented preference."""
    liked = [r for r in rows if r["helpful"]]
    disliked = [r for r in rows if not r["helpful"]]
    reasons = [x for r in rows for x in r.get("reasons", [])]
    too_long, too_short = reasons.count(REASON_TOO_LONG), reasons.count(REASON_TOO_SHORT)
    hints: list[str] = []
    length = None
    if len(liked) >= 3 and len(disliked) >= 2:
        wl, wd = [_words(r["answer"]) for r in liked], [_words(r["answer"]) for r in disliked]
        ml, md = statistics.median(wl), statistics.median(wd)
        mid = (ml + md) / 2
        share = lambda xs, test: sum(test(x) for x in xs) / len(xs)
        if md and ml <= 0.7 * md and share(wl, lambda x: x <= mid) >= 0.7 and share(wd, lambda x: x > mid) >= 0.7:
            length = "short"                                  # at least 70% of EACH group sits on its own side, not just the medians
        elif ml and md and ml >= 1.4 * md and share(wl, lambda x: x >= mid) >= 0.7 and share(wd, lambda x: x < mid) >= 0.7:
            length = "detailed"
    if length is None and too_long >= 2 and too_long > too_short:
        length = "short"
    if length is None and too_short >= 2 and too_short > too_long:
        length = "detailed"
    if length == "short":
        hints.append("short, to-the-point answers")
    elif length == "detailed":
        hints.append("detailed, step-by-step answers")
    if len(liked) >= 3 and len(disliked) >= 2:
        fl = sum(_has_list(r["answer"]) for r in liked) / len(liked)
        fd = sum(_has_list(r["answer"]) for r in disliked) / len(disliked)
        if fl >= 0.7 and fd <= 0.4:
            hints.append("bullet points or numbered steps")
        elif fl <= 0.3 and fd >= 0.6:
            hints.append("plain paragraphs without lists")
    return hints
