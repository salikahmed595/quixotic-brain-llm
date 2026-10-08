"""Discord import — PRD §17.2 pipeline:

JSON upload -> store raw JSON (S3 /raw/discord/) -> parse conversations -> remove system messages ->
detect customer/agent -> anonymize -> detect language -> extract objection / intent / stage / agent
response / outcome / sale value & discount -> quality signals -> embeddings -> store as sales memory.

The PRD does not define (1) the Discord export schema, (2) how customer/agent are told apart,
(3) how objection/intent/stage/outcome are extracted or (4) what "quality signals" are. Those are the two
plug-in points below (`ConversationParser`, `MemoryExtractor`); the job fails with a clear message until
they are configured (docs/PRD_GAPS.md).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable, Optional, Protocol, Sequence
from uuid import UUID

from ..retrieval.embeddings import Embedder
from ..retrieval.language import LanguageService
from .anonymize import Anonymizer
from .schema import SalesMemoryRecord


class NotConfigured(RuntimeError):
    pass


STRUCTURED_BATCH = 32                    # implementation necessity: records embedded per model call (docs/PRD_GAPS.md)
_ALIASES = {"stage": "sales_stage"}      # owner's export names the §16.2 `sales_stage` field `stage`


def parse_structured(raw: bytes) -> Optional[list[SalesMemoryRecord]]:
    """Owner request (2026-10-08): a JSON list of already-extracted sales memories (§16.2 fields, one object per
    customer message / agent response) is imported as-is. Returns None when the file is not in that shape, so the
    Discord-export path (parser + extractor) is used instead."""
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not (isinstance(data, list) and data and all(isinstance(r, dict) for r in data)
            and any("customer_message" in r or "agent_response" in r for r in data)):
        return None
    fields = SalesMemoryRecord.model_fields
    out = []
    for r in data:
        rec = {_ALIASES.get(k, k): v for k, v in r.items()}
        rec = {k: (str(v) if k == "conversation_id" and v is not None else v) for k, v in rec.items() if k in fields}
        out.append(SalesMemoryRecord(**rec))
    return out


@dataclass
class Message:
    author: str                 # the Discord username (anonymized away)
    role: str                   # "customer" | "agent" — decided by the parser (§17.2 "Detect Customer / Agent")
    text: str
    is_system: bool = False     # §17.2 "Remove System Messages"


@dataclass
class Conversation:
    id: str
    messages: list[Message] = field(default_factory=list)


class ConversationParser(Protocol):
    def parse(self, raw: bytes) -> list[Conversation]: ...


class MemoryExtractor(Protocol):
    def extract(self, conversation: Conversation) -> list[SalesMemoryRecord]:
        """Receives the already-anonymized conversation; returns §16.2 records."""


class MemoryStore(Protocol):
    def insert_sales_memory(self, rec: dict, embedding: Sequence[float], model: str, department_id: UUID,
                            job_id: Optional[UUID] = None) -> UUID: ...


class SalesMemoryImporter:
    def __init__(self, store: MemoryStore, embedder: Embedder, language: LanguageService,
                 parser: Optional[ConversationParser], extractor: Optional[MemoryExtractor]) -> None:
        self.store, self.embedder, self.language = store, embedder, language
        self.parser, self.extractor = parser, extractor

    def run(self, raw: bytes, department_id: UUID, job_id: Optional[UUID] = None, on_progress=None) -> int:
        records = parse_structured(raw)
        if records is not None:                          # already-extracted §16.2 records: no parser/extractor needed
            return self.run_structured(records, department_id, job_id, on_progress)
        if self.parser is None:
            raise NotConfigured("no Discord export parser configured: the PRD does not define the export schema")
        if self.extractor is None:
            raise NotConfigured("no memory extractor configured: the PRD does not define how objection/intent/"
                                "stage/outcome are extracted")
        conversations = self.parser.parse(raw)
        total, stored = len(conversations), 0
        if on_progress:
            on_progress(0, total)
        for n, conv in enumerate(conversations, 1):
            for rec in self.extractor.extract(self._anonymized(conv)):
                text = rec.embedding_text()
                if not text:
                    continue
                if not rec.language:
                    rec.language = self.language.detect(text)
                self.store.insert_sales_memory(rec.model_dump(), self.embedder.embed(text), self.embedder.name,
                                               department_id, job_id)
                stored += 1
            if on_progress:
                on_progress(n, total)
        return stored

    def run_structured(self, records: list[SalesMemoryRecord], department_id: UUID, job_id: Optional[UUID] = None,
                       on_progress=None) -> int:
        """§17.2 steps that still apply to records that were extracted elsewhere: anonymize, detect language,
        generate embeddings, store as sales memory. Embedded in batches (CPU, §24)."""
        anon = Anonymizer()
        todo = []
        for rec in records:
            for f in ("customer_message", "agent_response", "customer_objection"):
                val = getattr(rec, f)
                if val:
                    setattr(rec, f, anon.clean(val))
            text = rec.embedding_text()
            if text:
                if not rec.language:
                    rec.language = self.language.detect(text)
                todo.append((rec, text))
        total, stored = len(todo), 0
        if on_progress:
            on_progress(0, total)
        for i in range(0, total, STRUCTURED_BATCH):
            batch = todo[i:i + STRUCTURED_BATCH]
            for (rec, _), emb in zip(batch, self.embedder.embed_many([t for _, t in batch])):
                self.store.insert_sales_memory(rec.model_dump(), emb, self.embedder.name, department_id, job_id)
                stored += 1
            if on_progress:
                on_progress(stored, total)
        return stored

    def _anonymized(self, conv: Conversation) -> Conversation:
        anon = Anonymizer(usernames=[m.author for m in conv.messages])
        msgs = [Message(author="[USER]", role=m.role, text=anon.clean(m.text)) for m in conv.messages if not m.is_system]
        return Conversation(id=conv.id, messages=msgs)
