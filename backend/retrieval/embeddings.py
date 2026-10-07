"""Embedding layer — PRD §24. The rest of the app depends only on `Embedder` (`embed(text)`)."""
from __future__ import annotations

import threading
from typing import Protocol, Sequence

from ..config import EMBEDDING_DIM, Settings


class Embedder(Protocol):
    name: str          # stored on every chunk so a model change can be re-indexed (§24.2)
    dim: int

    def embed(self, text: str) -> list[float]: ...
    def embed_many(self, texts: Sequence[str]) -> list[list[float]]: ...


class BGEM3Embedder:
    """BAAI/bge-m3 dense embeddings (PRD §24.1 'initial recommended model to evaluate')."""
    name = "bge-m3"
    dim = EMBEDDING_DIM

    def __init__(self, model_path: str = "BAAI/bge-m3") -> None:
        self._path, self._model, self._lock = model_path, None, threading.Lock()

    def _load(self):
        with self._lock:               # warm-up thread and a first request must not both load the model
            if self._model is None:
                from sentence_transformers import SentenceTransformer  # heavy; imported lazily
                self._model = SentenceTransformer(self._path, device="cpu")   # CPU first; no GPU cluster (stack decision)
        return self._model

    def warm(self) -> None:
        self.embed("warm up")

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        vecs = self._load().encode(list(texts), normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]


def get_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "bge-m3":
        return BGEM3Embedder(settings.embedding_model_path)
    # PRD §24.2 names multilingual E5, GTE multilingual and Qwen only as future migration targets.
    raise NotImplementedError(
        f"embedding provider {settings.embedding_provider!r} is not implemented; "
        "PRD §24.2 lists other models only as future options"
    )
