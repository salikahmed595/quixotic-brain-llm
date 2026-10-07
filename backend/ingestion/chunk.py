"""Chunk content (PRD §13.3). The PRD gives no chunking strategy, so size and overlap are required
configuration (QB_CHUNK_SIZE / QB_CHUNK_OVERLAP, both in characters). Chunks never cross a section."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .extract import Block


@dataclass
class Piece:
    section: Optional[str]
    text: str


_SENTENCE_END = (". ", "! ", "? ", "۔ ", "؟ ", ".\n", "!\n", "?\n", "۔\n", "\n\n")


def _cut_point(text: str, start: int, end: int, size: int) -> int:
    """Where to end a chunk that would otherwise be cut at `end`. Prefer the last sentence end in the second half of the
    window (so an answer is not split mid-sentence), then the last whitespace, then the hard limit."""
    floor = start + size // 2
    best = max((text.rfind(t, floor, end) + len(t) - 1 for t in _SENTENCE_END if text.rfind(t, floor, end) != -1), default=-1)
    if best > start:
        return best
    cut = max(text.rfind(" ", start + 1, end), text.rfind("\n", start + 1, end))
    return cut if cut > start else end


def _windows(text: str, size: int, overlap: int) -> list[str]:
    out, n, start = [], len(text), 0
    while start < n:
        end = min(start + size, n)
        if end < n:
            end = _cut_point(text, start, end, size)
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= n:
            break
        nxt = end - overlap
        start = nxt if nxt > start else end           # always make progress
        while start < n and start > 0 and not text[start - 1].isspace() and not text[start].isspace():
            start += 1                                # start on a word boundary
    return out


def chunk_blocks(blocks: list[Block], size: int, overlap: int) -> list[Piece]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("chunk size must be > 0 and overlap in [0, size)")
    return [Piece(b.section, t) for b in blocks for t in _windows(b.text, size, overlap)]
