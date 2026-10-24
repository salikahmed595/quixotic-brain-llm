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
    database_url: str                      # PostgreSQL + pgvector (PRD §8, §11)
    s3_bucket: str                         # private object storage for uploaded originals (PRD §11)
    queue_backend: str                     # PRD §11 "Redis and worker queue": "redis" (EC2, owner) or "sqs" (AWS managed)
    redis_url: Optional[str] = None        # required for redis, e.g. redis://redis:6379/0
    sqs_queue_url: Optional[str] = None    # required for sqs
    aws_region: Optional[str] = None
    s3_endpoint_url: Optional[str] = None  # only for local emulators
    sqs_endpoint_url: Optional[str] = None
    raw_storage_dir: Optional[str] = None  # LOCAL DEVELOPMENT ONLY: keep raw files in this folder instead of S3 (docs/PRD_GAPS.md)

    # ---- implementation necessities (not in PRD; see docs/PRD_GAPS.md) ----------------
    session_secret: str                    # HS256 signing key (>= 32 chars)
    session_ttl_seconds: int               # PRD §5 FR-AUTH-06 "session expiry" without a number

    # ---- accounts (PRD §5) — values the PRD does not give are required -------------------------------------------
    public_url: str                        # e.g. https://ai.example.com — links in emails; https => Secure cookies
    one_time_link_ttl_seconds: int         # FR-AUTH-02 / FR-AUTH-06 verification + reset links: lifetime not specified
    admin_mfa_required: bool               # FR-AUTH-06 "admin MFA"; false only for local development
    field_encryption_key: str              # PRD §10 encryption at rest: protects MFA secrets (>= 32 characters)
    mail_backend: str                      # FR-AUTH-02: "smtp" (real email) or "console" (local dev: links go to the log)
    mail_from: Optional[str] = None        # required for smtp, e.g. "Quixotic AI <no-reply@example.com>"
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_starttls: bool = True             # port 587 style (STARTTLS)
    smtp_ssl: bool = False                 # port 465 style (implicit TLS, e.g. Hostinger); then smtp_starttls is ignored

    # ---- knowledge model (PRD §8) — values the PRD does not give are required ------------------------------------
    vault_dir: str                         # §8/§11 versioned Markdown vault: a Git repository on the server (created if missing)
    # §8 "sensitivity/access scope" without levels: JSON {level: [roles allowed to see it]}, e.g.
    # {"internal": ["employee", ...], "confidential": ["knowledge_admin", "system_admin"]}. Retrieval filters on it (§10).
    sensitivity_levels_json: str

    # ---- Obsidian contributors (PRD §9; optional — off unless configured) ----------------------------------------------------
    vault_hook_secret: Optional[str] = None           # >= 32 chars; signs the Obsidian Git hook calls. Unset = vault/push endpoint off.
    # Owner request 2026-10-20: one private repository per Obsidian contributor (backend/knowledge/contributors.py). Unset = off.
    vault_contributors_dir: Optional[str] = None
    vault_remote: Optional[str] = None                # bare Git repository the CEO's Obsidian syncs with

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

    # Overload protection (QA 2026-10-19): seconds a request may wait for the CPU models before a 503 "busy". Unset = no limit.
    model_queue_timeout_seconds: Optional[float] = None

    # Owner-approved addition 2026-10-20 (docs/PRD_GAPS.md §0): "Translate for client" is offered to members of these departments
    # (comma-separated names, e.g. "Sales - Upseller,Sales - Fresh Seller"). Unset = the tool is off.
    translate_departments: Optional[str] = None

    @property
    def translate_department_names(self) -> frozenset[str]:
        return frozenset(n.strip().lower() for n in (self.translate_departments or "").split(",") if n.strip())

    # Restate Urdu / Roman Urdu / mixed questions as an English search query with one small LLM call (PRD §23). Optional.
    query_interpretation: bool = False
    feedback_learning: bool = True         # owner request: learn from 👍/👎 (retrieval order + personal style); docs/PRD_GAPS.md
    # Owner request (2026-10-08): past sales chats (§16) are used in every Ask mode, and when no approved knowledge covers a
    # question an answer is written from them alone, clearly labelled as not policy. Only past chats at least this similar
    # (cosine) to the question are used. Unset = the PRD behaviour: history only in Sales Coach, never answering alone.
    sales_history_min_similarity: Optional[float] = None
    # Owner decision (2026-10-17): past sales chats are OFF — answers come only from approved knowledge (PRD §1, §7, §8).
    # While False, no past chat is retrieved in any mode and `sales_history_min_similarity` has no effect.
    sales_history_enabled: bool = False
    # Owner 2026-10-21: a "what should I reply to the client?" question with no policy and no matching past chat gets careful,
    # labelled advice that follows the selling boundaries (never prices/discounts/deadlines). False = PRD §6 FR-CHAT-04 reply.
    general_guidance: bool = False
    # Owner 2026-10-21: answer everything like a general assistant; company knowledge, past chats and boundaries are context.
    # Company facts still only from approved knowledge. False = strict PRD behaviour (§6 FR-CHAT-04).
    general_assistant: bool = False
    # Owner 2026-10-24: a Web Search toggle in the chat. Off by default per question; the user turns it on. Needs the OpenAI
    # provider (its built-in web_search tool). False = the toggle is refused (PRD §14 keeps Web Search governed).
    web_search_enabled: bool = False
    # Owner 2026-10-24: "generate images the user asks for". OpenAI image model (measured: gpt-image-1-mini works on this
    # account, gpt-image-1 does not exist for it). Unset = image creation off. Quality: low | medium | high (cost and speed).
    image_model: Optional[str] = None
    image_quality: str = "medium"

    # ---- pluggable providers (PRD §24, §27, §28) -------------------------------------
    embedding_provider: str = "bge-m3"     # PRD §24.1 initial model to evaluate
    embedding_model_path: str = "BAAI/bge-m3"   # HF id (downloaded on first use) or a local folder, e.g. .models/bge-m3
    reranker_provider: Optional[str] = None  # unset = no reranker (PRD Phase 1 has none)
    reranker_model: Optional[str] = None
    generation_provider: str               # PRD §28 lists several; none is chosen
    generation_model_id: Optional[str] = None
    generation_max_tokens: Optional[int] = None  # required by the Claude API; the PRD sets no answer length
    # OpenAI reasoning models only (gpt-5 family, o-series): minimal | low | medium | high. Unset = the model's default.
    # Lower is faster (PRD §2: p95 answer < 8 s); higher thinks longer.
    generation_reasoning_effort: Optional[str] = None

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

    @field_validator("field_encryption_key")
    @classmethod
    def _enc(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("field_encryption_key must be at least 32 characters")
        return v

    @field_validator("public_url")
    @classmethod
    def _url(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError("public_url must start with https:// (or http:// for local development)")
        return v.rstrip("/")

    @field_validator("mail_backend")
    @classmethod
    def _mail(cls, v: str) -> str:
        if v not in ("smtp", "console"):
            raise ValueError("mail_backend must be 'smtp' or 'console'")
        return v

    @field_validator("sensitivity_levels_json")
    @classmethod
    def _levels(cls, v: str) -> str:
        from .permissions.roles import Role
        try:
            data = json.loads(v)
        except ValueError:
            raise ValueError("sensitivity_levels_json must be JSON: {level: [role, ...]}")
        roles = {r.value for r in Role}
        if not isinstance(data, dict) or not data:
            raise ValueError("sensitivity_levels_json needs at least one level")
        for level, allowed in data.items():
            if not isinstance(allowed, list) or not allowed or not set(allowed) <= roles:
                raise ValueError(f"sensitivity level {level!r}: list one or more of {sorted(roles)}")
            if level == "unclassified":
                raise ValueError("'unclassified' is reserved for documents nobody has classified yet (never retrievable)")
        return v

    @property
    def sensitivity_levels(self) -> dict[str, frozenset[str]]:
        return {k: frozenset(v) for k, v in json.loads(self.sensitivity_levels_json).items()}

    def levels_for(self, role: str) -> frozenset[str]:
        """Sensitivity levels this role may retrieve (PRD §10: confidentiality filters apply before retrieval)."""
        return frozenset(level for level, roles in self.sensitivity_levels.items() if role in roles)

    @property
    def secure_cookies(self) -> bool:
        return self.public_url.startswith("https://")

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
        if self.sales_history_min_similarity is not None and not 0 <= self.sales_history_min_similarity <= 1:
            raise ValueError("sales_history_min_similarity must be between 0 and 1")
        if not 1 <= self.rerank_top_k <= self.candidate_count:
            raise ValueError("require 1 <= rerank_top_k <= candidate_count")
        if self.generation_reasoning_effort not in (None, "", "minimal", "low", "medium", "high"):
            raise ValueError("generation_reasoning_effort must be minimal, low, medium or high")
        if self.queue_backend not in ("redis", "sqs"):
            raise ValueError("queue_backend must be 'redis' or 'sqs'")
        if self.queue_backend == "redis" and not self.redis_url:
            raise ValueError("queue_backend=redis needs redis_url")
        if self.queue_backend == "sqs" and not self.sqs_queue_url:
            raise ValueError("queue_backend=sqs needs sqs_queue_url")
        if self.mail_backend == "smtp" and not (self.smtp_host and self.smtp_port and self.mail_from):
            raise ValueError("mail_backend=smtp needs smtp_host, smtp_port and mail_from")
        for name in ("vault_hook_secret",):
            v = getattr(self, name)
            if v is not None and len(v) < 32:
                raise ValueError(f"{name} must be at least 32 characters")
        if self.one_time_link_ttl_seconds < 60:
            raise ValueError("one_time_link_ttl_seconds must be at least 60")
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
