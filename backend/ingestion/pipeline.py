"""Processing pipeline — PRD §13.3:
Store original -> Extract text -> Clean text -> Chunk -> Attach metadata -> Embeddings ->
Keyword index (generated column on `chunks`) -> Store -> Available for retrieval.

Chunks stay invisible to retrieval until the version's status is `active` (§15)."""
from __future__ import annotations

from typing import Protocol, Sequence
from uuid import UUID

from ..config import Settings
from ..retrieval.embeddings import Embedder
from ..retrieval.language import LanguageService
from .chunk import chunk_blocks
from .extract import extract_blocks, markdown_blocks


def embedding_text(title: str, section: str | None, text: str) -> str:
    """What gets embedded for a chunk: the document title and section heading travel with the text. Measured on 44 labelled
    questions (real BGE-M3): vector top-1 accuracy 0.76 -> 0.89, MRR 0.85 -> 0.91. The stored/shown text stays unchanged."""
    head = f"{title} - {section}" if section else title
    return f"{head}\n{text}"


class NoReadableText(ValueError):
    """The file was valid but contained no text to index."""


class IngestionStore(Protocol):
    def version_bundle(self, version_id: UUID) -> dict: ...
    def replace_chunks(self, version_id: UUID, rows: Sequence[dict]) -> None: ...
    def set_file_status(self, file_id: UUID, status: str, error: str | None = None) -> None: ...


class RawStorage(Protocol):
    def get(self, key: str) -> bytes: ...


class IngestionService:
    def __init__(self, store: IngestionStore, storage: RawStorage, embedder: Embedder,
                 language: LanguageService, settings: Settings) -> None:
        self.store, self.storage, self.embedder = store, storage, embedder
        self.language, self.settings = language, settings

    def process_version(self, version_id: UUID) -> int:
        """(Re)build the chunks of one knowledge version. Returns the number of chunks stored."""
        b = self.store.version_bundle(version_id)
        file_id = b.get("source_file_id")
        try:
            if file_id:
                self.store.set_file_status(file_id, "processing")
                blocks = extract_blocks(b["extension"], self.storage.get(b["s3_key"]))
            else:
                blocks = markdown_blocks(b.get("body") or "")
            pieces = chunk_blocks(blocks, self.settings.chunk_size, self.settings.chunk_overlap)
            if not pieces:      # never report "ready" for a document that cannot answer anything
                raise NoReadableText("No readable text was found in this file. Scanned or image-only PDFs are not supported "
                                     "yet; upload a text version instead.")
            vectors = self.embedder.embed_many([embedding_text(b["title"], p.section, p.text) for p in pieces])
            doc_language = b.get("language") or self.language.detect(" ".join(p.text for p in pieces)[:2000])
            base_meta = {                                                       # PRD §14
                "company": self.settings.tenant_id,
                "department": b["departments"],
                "document_type": b.get("document_type"),
                "category": b.get("category"),
                "access_level": b.get("access_level"),
                "status": b["status"],
                "version": b["version"],
                "language": doc_language,
                "created_at": b["created_at"].date().isoformat(),
                "updated_at": b["updated_at"].date().isoformat(),
            }
            rows = [{"chunk_index": i, "section": p.section, "text": p.text, "metadata": base_meta,
                     "embedding": v, "embedding_model": self.embedder.name}
                    for i, (p, v) in enumerate(zip(pieces, vectors))]
            self.store.replace_chunks(version_id, rows)
            if file_id:
                self.store.set_file_status(file_id, "ready")
            return len(rows)
        except Exception as exc:
            if file_id:
                self.store.set_file_status(file_id, "failed", str(exc)[:500])
            raise
