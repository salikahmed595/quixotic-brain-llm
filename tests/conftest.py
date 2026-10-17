import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import Settings  # noqa: E402

BASE = dict(
    database_url="postgresql://x", s3_bucket="b", sqs_queue_url="q", session_secret="test-secret-test-secret-test-secret-123", session_ttl_seconds=3600,
    max_upload_bytes=1000, chunk_size=100, chunk_overlap=20, candidate_count=20, final_chunk_count=5,
    rerank_top_k=8, historical_top_k=5, roman_urdu_min_ratio=0.5, confidence_high=0.8, confidence_medium=0.5, confidence_vector_high=0.8, confidence_vector_medium=0.5,
    generation_provider="bedrock",
    public_url="http://testserver", one_time_link_ttl_seconds=3600, admin_mfa_required=False,
    field_encryption_key="test-field-key-test-field-key-123456", mail_backend="console",
    vault_dir=".pytest-vault", sensitivity_levels_json='{"internal": ["employee", "department_reviewer", "knowledge_admin", '
    '"system_admin", "founder_ceo"], "confidential": ["knowledge_admin", "system_admin", "founder_ceo"]}',
)


def make_settings(**over) -> Settings:
    return Settings(_env_file=None, **{**BASE, **over})
