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

from dataclasses import dataclass, field
from typing import Iterable, Optional, Protocol, Sequence
from uuid import UUID

from ..retrieval.embeddings import Embedder
from ..retrieval.language import LanguageService
from .anonymize import Anonymizer
from .schema import SalesMemoryRecord


class NotConfigured(RuntimeError):
    pass


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

    def _anonymized(self, conv: Conversation) -> Conversation:
        anon = Anonymizer(usernames=[m.author for m in conv.messages])
        msgs = [Message(author="[USER]", role=m.role, text=anon.clean(m.text)) for m in conv.messages if not m.is_system]
        return Conversation(id=conv.id, messages=msgs)
