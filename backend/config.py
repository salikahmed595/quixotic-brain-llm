"""Runtime configuration.

PRD rule (CLAUDE.md, Rule 1): values the PRD does not specify have NO hidden default here.
They are required settings; the app refuses to start without them. See docs/PRD_GAPS.md.
Environment variables are prefixed QB_ (see .env.example).
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# PRD §27 / §7: hybrid search returns ~20–40 candidates, reranker keeps 5–8.
CANDIDATE_RANGE = (20, 40)
FINAL_RANGE = (5, 8)
# PRD §24.1: BGE-M3 dense vectors are 1024-d. Changing the model needs a migration + re-index (§24.2).
EMBEDDING_DIM = 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QB_", env_file=".env", extra="ignore")

    # PRD §66: tenant_id is introduced early; Quixotic is the only initial tenant.
    tenant_id: str = "quixotic"

    # ---- infrastructure (PRD §44–§46) -------------------------------------------------
    database_url: str                      # RDS PostgreSQL + pgvector
    s3_bucket: str                         # private bucket; paths per §46
    sqs_queue_url: str                     # background jobs (§47)
    aws_region: Optional[str] = None
    s3_endpoint_url: Optional[str] = None  # only for local emulators
    sqs_endpoint_url: Optional[str] = None
    raw_storage_dir: Optional[str] = None  # LOCAL DEVELOPMENT ONLY: keep raw files in this folder instead of S3 (docs/PRD_GAPS.md)

    # ---- implementation necessities (not in PRD; see docs/PRD_GAPS.md) ----------------
    session_secret: str                    # signs login tokens
    session_ttl_seconds: int               # PRD §41 names no session lifetime

    # ---- ingestion (PRD §13) — PRD gives no sizes ------------------------------------
    max_upload_bytes: int                  # PRD §51 "Upload size limits" without a number
    chunk_size: int                        # PRD §13.3 "Chunk Content" without a strategy
    chunk_overlap: int

    # ---- retrieval (PRD §7, §26, §27) ------------------------------------------------
    candidate_count: int                   # 20–40
    final_chunk_count: int                 # 5–8
    rerank_top_k: int                      # how many of the hybrid candidates the reranker reads (cost: ~0.5 s each on CPU)
    historical_top_k: int                  # PRD §11.3 "retrieve historical sales examples" — no K given
    roman_urdu_min_ratio: float            # PRD §22 defines 4 languages, not the boundary

    # ---- confidence (PRD §31–§32): backend scores, frontend labels ------------------
    confidence_high: float                 # reranker probability: High at or above this
    confidence_medium: float               # reranker probability: Medium at or above this
    confidence_vector_high: float          # vector (cosine) similarity: High at or above this
    confidence_vector_medium: float        # vector (cosine) similarity: Medium at or above this

    # Skip the reranker when retrieval is decisive: top-1 vector similarity leads top-2 by at least this much (0 = never skip).
    # Measured: 0.04 skips it for ~54% of questions with the same result quality and no unanswerable question let through.
    rerank_skip_margin: float = 0.0

    # Restate Urdu / Roman Urdu / mixed questions as an English search query with one small LLM call (PRD §23). Optional.
    query_interpretation: bool = False
    feedback_learning: bool = True         # owner request: learn from 👍/👎 (retrieval order + personal style); docs/PRD_GAPS.md

    # ---- pluggable providers (PRD §24, §27, §28) -------------------------------------
    embedding_provider: str = "bge-m3"     # PRD §24.1 initial model to evaluate
    embedding_model_path: str = "BAAI/bge-m3"   # HF id (downloaded on first use) or a local folder, e.g. .models/bge-m3
    reranker_provider: Optional[str] = None  # unset = no reranker (PRD Phase 1 has none)
    reranker_model: Optional[str] = None
    generation_provider: str               # PRD §28 lists several; none is chosen
    generation_model_id: Optional[str] = None
    generation_max_tokens: Optional[int] = None  # required by the Claude API; the PRD sets no answer length

    # ---- knowledge priority (PRD §20) -----------------------------------------------
    # PRD names the four tiers but not which document_type belongs to which. JSON object,
    # e.g. {"policy":1}. Empty = tier ordering not applied.
    priority_tiers_json: str = "{}"

    @field_validator("session_secret")
    @classmethod
    def _secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("session_secret must be at least 32 characters (HS256 JWT signing key)")
        return v

    @field_validator("candidate_count")
    @classmethod
    def _cand(cls, v: int) -> int:
        lo, hi = CANDIDATE_RANGE
        if not lo <= v <= hi:
            raise ValueError(f"PRD §27: candidate_count must be {lo}–{hi}")
        return v

    @field_validator("final_chunk_count")
    @classmethod
    def _final(cls, v: int) -> int:
        lo, hi = FINAL_RANGE
        if not lo <= v <= hi:
            raise ValueError(f"PRD §27: final_chunk_count must be {lo}–{hi}")
        return v

    @model_validator(mode="after")
    def _cross(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if not 0 <= self.confidence_medium <= self.confidence_high:
            raise ValueError("require 0 <= confidence_medium <= confidence_high")
        if not 0 <= self.confidence_vector_medium <= self.confidence_vector_high <= 1:
            raise ValueError("require 0 <= confidence_vector_medium <= confidence_vector_high <= 1")
        if not 1 <= self.rerank_top_k <= self.candidate_count:
            raise ValueError("require 1 <= rerank_top_k <= candidate_count")
        if self.reranker_provider and not self.reranker_model:
            raise ValueError("reranker_provider is set but reranker_model is not (PRD names no model)")
        return self

    @property
    def priority_tiers(self) -> dict[str, int]:
        return {str(k): int(v) for k, v in json.loads(self.priority_tiers_json).items()}


@lru_cache
def get_settings() -> Settings:
    # Make every variable in .env visible to the process, not only the QB_* ones: the answer-model SDKs read
    # their own standard names (OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY). Real environment variables win.
    from dotenv import load_dotenv
    load_dotenv()
    return Settings()  # raises a pydantic ValidationError listing every missing value
