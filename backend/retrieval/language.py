"""Language detection and Roman Urdu normalization — PRD §22, §23.

Supported: english, urdu, roman_urdu, mixed. The original query is always kept next to the
normalized one for audit/debugging (§23).
The PRD gives only the §23 normalization example, so the lexicon file holds exactly that
(`data/roman_urdu_lexicon.json`) and is meant to be extended by the company.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

ENGLISH, URDU, ROMAN_URDU, MIXED, UNKNOWN = "english", "urdu", "roman_urdu", "mixed", "unknown"
_ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_WORD = re.compile(r"[A-Za-z]+")
DEFAULT_LEXICON = Path(__file__).resolve().parent.parent / "data" / "roman_urdu_lexicon.json"


# Function words that carry no topic. Used only to build the KEYWORD query: with them every chunk matched on "is | our | what"
# (measured: removing them took the keyword leg from R@5 0.52 to 0.74). English list is generic; Roman Urdu words come
# from the lexicon markers (docs/PRD_GAPS.md).
STOPWORDS_EN = frozenset(("a an the is are was were be been to of in on for and or do does did we our you your i my it its this that these "
                          "those what how when who whom which can could should will would at with as by from if so than then there here "
                          "about into over under").split())


@dataclass(frozen=True)
class NormalizedQuery:
    original: str          # kept for audit (PRD §23)
    normalized: str        # spelling-normalised (PRD §23)
    language: str
    search_text: str = ""  # normalized + English meaning of known Roman Urdu phrases: what retrieval actually searches with


class LanguageService:
    def __init__(self, min_roman_ratio: float, lexicon_path: Path = DEFAULT_LEXICON, vocab_loader=None, vocab_ttl: float = 60.0):
        data = json.loads(Path(lexicon_path).read_text(encoding="utf-8"))
        self._map = {k.lower(): v for k, v in data["normalize"].items()}
        self._markers = {m.lower() for m in data["markers"]}
        self._file_expand = {k.lower(): v for k, v in data.get("expand", {}).items()}
        self._expand = dict(self._file_expand)
        self.stopwords = STOPWORDS_EN | self._markers
        self._ratio = min_roman_ratio
        # Words the company taught through the Vocabulary screen (owner request). Re-read every `vocab_ttl` seconds so a new word
        # reaches every running server without a restart.
        self._vocab_loader, self._vocab_ttl, self._vocab_at = vocab_loader, vocab_ttl, float("-inf")

    def refresh_vocabulary(self) -> None:
        rows = self._vocab_loader() if self._vocab_loader else []
        taught = {r["phrase"].strip().lower(): r["meaning"].strip() for r in rows if r["phrase"].strip() and r["meaning"].strip()}
        self._expand = {**self._file_expand, **taught}                   # taught words override the built-in table
        self._vocab_at = time.monotonic()

    def _fresh_vocabulary(self) -> None:
        if self._vocab_loader and time.monotonic() - self._vocab_at >= self._vocab_ttl:   # >=: Windows' clock ticks ~15 ms
            try:
                self.refresh_vocabulary()
            except Exception:                                            # database hiccup: keep the words we already have
                self._vocab_at = time.monotonic()

    def detect(self, text: str) -> str:
        words = [w.lower() for w in _WORD.findall(text)]
        if _ARABIC.search(text):
            return MIXED if words else URDU
        if not words:
            return UNKNOWN
        hits = sum(w in self._markers for w in words)
        if hits == 0:
            return ENGLISH
        return ROMAN_URDU if hits / len(words) >= self._ratio else MIXED

    def normalize(self, text: str) -> str:
        return _WORD.sub(lambda m: self._map.get(m.group(0).lower(), m.group(0)), text)

    def expand(self, normalized: str) -> str:
        """Append the English meaning of company-defined Roman Urdu phrases (lexicon `expand`), e.g. 'paise wapas' -> 'refund'."""
        self._fresh_vocabulary()
        low = normalized.lower()
        extra = [en for phrase, en in self._expand.items() if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", low)]
        return normalized + (" " + " ".join(extra) if extra else "")

    def keyword_terms(self, text: str) -> str:
        """The text the keyword (sparse) leg searches with: topic words only. Falls back to all words if nothing is left."""
        words = re.findall(r"\w+", text, flags=re.UNICODE)
        kept = [w for w in words if w.lower() not in self.stopwords]
        return " ".join(kept or words)

    def process(self, query: str) -> NormalizedQuery:
        norm = self.normalize(query)
        return NormalizedQuery(original=query, normalized=norm, language=self.detect(query), search_text=self.expand(norm))
