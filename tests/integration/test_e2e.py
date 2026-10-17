"""End-to-end: HTTP API -> S3 -> SQS -> worker -> PostgreSQL/pgvector -> search/ask.

Real: FastAPI app, auth (server-side sessions), PostgreSQL + pgvector, the SQL stores, ingestion, the worker loop.
Mocked: S3/SQS (moto), the answer model (no LLM key available) and - unless the weights are on disk - the embedder.
Set QB_TEST_DATABASE_URL to run. Put the models in .models/ (scripts/download_models.sh) to use BGE-M3 and the reranker."""
import os
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from backend.analytics.dashboard import AnalyticsStore
from backend.api.services import Services
from backend.auth.security import SlidingWindowLimiter, hash_password
from backend.database.accounts import OneTimeTokenStore, SessionStore, SystemSettingsStore
from backend.database.conversations import ConversationStore
from backend.database.knowledge import KnowledgeStore
from backend.database.ops import OpsStore
from backend.database.retrieval_store import RetrievalSQLStore
from backend.database.users import UserStore
from backend.ingestion.pipeline import IngestionService
from backend.ingestion.storage import S3Storage, SQSQueue
from backend.main import create_app
from backend.notifications.mail import ConsoleMailer
from backend.permissions.roles import Role
from backend.reranking.base import CrossEncoderReranker
from backend.retrieval.ask import AskService
from backend.retrieval.embeddings import BGEM3Embedder
from backend.retrieval.language import LanguageService
from backend.retrieval.search import SearchService
from backend.sales_memory.importer import SalesMemoryImporter
from tests.conftest import make_settings
from tests.fakes import FakeGenerator
from tests.integration.conftest import HashEmbedder
from workers.worker import run_once

pytestmark = pytest.mark.skipif(not os.environ.get("QB_TEST_DATABASE_URL"), reason="needs a real PostgreSQL")
ROOT = Path(__file__).resolve().parents[2]
M3, RR = ROOT / ".models" / "bge-m3", ROOT / ".models" / "bge-reranker-v2-m3"
REAL_MODELS = (M3 / "pytorch_model.bin").exists() and (RR / "model.safetensors").exists() and \
    (M3 / "pytorch_model.bin").stat().st_size > 2_270_000_000 and (RR / "model.safetensors").stat().st_size > 2_270_000_000

SALES_POLICY = b"""# Sales Pricing Policy

## 4.2 Discount Approval
Customers buying 3 or more artworks can receive up to 10% discount after manager approval.
A discount above 10% is not allowed.

## 4.3 Refunds
Refunds are reviewed against order status and delivery date before approval.
"""


@pytest.fixture
def stack(db, monkeypatch):
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "test")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="qb-e2e-bucket")
        qurl = boto3.client("sqs", region_name="us-east-1").create_queue(QueueName="qb-e2e")["QueueUrl"]
        s = make_settings(s3_bucket="qb-e2e-bucket", sqs_queue_url=qurl, aws_region="us-east-1", max_upload_bytes=1_000_000,
                          chunk_size=400, chunk_overlap=40, candidate_count=20, final_chunk_count=5,
                          confidence_high=0.01 if REAL_MODELS else 0.3, confidence_medium=0.001 if REAL_MODELS else 0.1,   # BGE reranker probabilities are small for short chunks
                          reranker_provider="cross-encoder" if REAL_MODELS else None,
                          reranker_model=str(RR) if REAL_MODELS else None)
        t = s.tenant_id
        users, knowledge, ops = UserStore(db, t), KnowledgeStore(db, t), OpsStore(db, t)
        emb = BGEM3Embedder(str(M3)) if REAL_MODELS else HashEmbedder()
        rr = CrossEncoderReranker(str(RR)) if REAL_MODELS else None
        lang, storage = LanguageService(s.roman_urdu_min_ratio), S3Storage(s)
        search = SearchService(RetrievalSQLStore(db, t), emb, rr, lang, s)
        svc = Services(settings=s, users=users, knowledge=knowledge, ops=ops, analytics=AnalyticsStore(db, t), search=search,
                       ask=AskService(search, FakeGenerator(), s), ingestion=IngestionService(knowledge, storage, emb, lang, s),
                       importer=SalesMemoryImporter(ops, emb, lang, None, None), storage=storage, queue=SQSQueue(s),
                       language=lang, embedder=emb, limiter=SlidingWindowLimiter(), pool=db,
                       sessions=SessionStore(db, t), one_time=OneTimeTokenStore(db), system_settings=SystemSettingsStore(db, t),
                       mailer=ConsoleMailer(), conversations=ConversationStore(db, t))
        yield svc, TestClient(create_app(svc))


def login(client, ident, pw="pw12345"):
    """Signs in through the real login route; the session token from the HttpOnly cookie is then sent as a Bearer token so one
    client can act as several people at once (non-browser clients use sessions the same way)."""
    r = client.post("/v1/auth/login", json={"identifier": ident, "password": pw})
    assert r.status_code == 200, r.text
    token = r.cookies["qb_session"]
    client.cookies.clear()
    return {"Authorization": "Bearer " + token}


def test_upload_process_search_ask(stack):
    svc, client = stack
    sales = svc.users.department_by_name("Sales")["id"]
    hr = svc.users.department_by_name("HR")["id"]
    svc.users.create_user("e2e_admin", "e2e_admin@q.ai", "Admin", hash_password("pw12345"), Role.SYSTEM_ADMIN, [])
    svc.users.create_user("e2e_sales", "e2e_sales@q.ai", "Sales Rep", hash_password("pw12345"), Role.EMPLOYEE, [sales])
    admin, rep = login(client, "e2e_admin"), login(client, "e2e_sales@q.ai")           # employee ID or email (§41)
    assert client.post("/v1/auth/login", json={"identifier": "e2e_sales", "password": "bad"}).status_code == 401

    # employee cannot upload (§9.1); admin uploads and publishes directly (§9.4)
    files = {"file": ("sales_policy.md", SALES_POLICY, "text/markdown")}
    assert client.post("/v1/documents", headers=rep, files=files, data={"department_ids": str(sales)}).status_code == 403
    bad = client.post("/v1/documents", headers=admin, files={"file": ("x.exe", b"MZ", "application/octet-stream")},
                      data={"department_ids": str(sales)})
    assert bad.status_code == 422
    up = client.post("/v1/documents", headers=admin, files=files, data={
        "department_ids": f"{sales}", "title": "Sales Pricing Policy", "category": "Pricing", "document_type": "policy",
        "access_level": "Sales + Managers", "status": "active"})
    assert up.status_code == 202, up.text
    doc_id = up.json()["document_id"]

    # upload returned immediately; the background worker processes it (§47, §56)
    listed = client.get("/v1/documents", headers=admin).json()["documents"]
    assert listed[0]["processing_status"] == "pending"
    handled = 0
    while run_once(svc, wait_seconds=0):
        handled += 1
    assert handled >= 1
    done = client.get("/v1/documents", headers=admin).json()["documents"][0]
    assert done["processing_status"] == "ready" and done["status"] == "active"
    jobs = client.get("/v1/admin/jobs", headers=admin).json()["jobs"]
    assert all(j["status"] == "succeeded" for j in jobs)

    # raw original stored in S3 under /raw/documents/ (§46)
    keys = [o["Key"] for o in boto3.client("s3", region_name="us-east-1").list_objects_v2(Bucket="qb-e2e-bucket")["Contents"]]
    assert keys and keys[0].startswith("raw/documents/")

    # search (§39): sales rep finds the policy; returns text/score/source only
    r = client.post("/v1/search", headers=rep, json={"question": "can we give 20% discount?"}).json()
    assert r["results"][0]["source"] == "Sales Pricing Policy" and "10% discount" in " ".join(x["text"] for x in r["results"][:3])
    assert set(r["results"][0]) == {"text", "score", "source"}

    # ask (§38): grounded answer, sources with section/version, confidence label; question logged with original text
    a = client.post("/v1/ask", headers=rep, json={"question": "can we give 20% discount?", "department": "sales"}).json()
    assert a["confidence"] in ("high", "medium") and a["answer"]
    assert a["sources"][0]["title"] == "Sales Pricing Policy" and a["sources"][0]["version"] == 1 and a["sources"][0]["section"]

    # an HR-only department question from a Sales-only user is refused before retrieval (§42)
    assert client.post("/v1/ask", headers=rep, json={"question": "leave", "department": "hr"}).status_code == 403

    # feedback (§21) stores outcome for a logged question
    fb = client.post("/v1/feedback", headers=rep, json={"query_id": a["query_id"], "helpful": True, "outcome": "sale_closed"})
    assert fb.status_code == 201

    # failed question (§35): nothing relevant -> low confidence -> visible to admin only (§9.4)
    miss = client.post("/v1/ask", headers=rep, json={"question": "zxqv blorptastic ungleeb"}).json()
    if miss["confidence"] == "low":
        assert miss["actions"] == ["ask_manager", "report_missing_knowledge", "search_documents"]
        assert any("zxqv" in f["original_query"] for f in client.get("/v1/failed-questions", headers=admin).json()["failed_questions"])
    assert client.get("/v1/failed-questions", headers=rep).status_code == 403

    # insights + audit trail (§34, §53)
    dash = client.get("/v1/dashboard", headers=admin).json()
    assert dash["knowledge_chunks"] >= 1 and dash["questions_this_week"] >= 2
    events = {e["event"] for e in client.get("/v1/audit-logs", headers=admin).json()["audit_logs"]}
    assert {"user_login", "failed_authentication", "document_upload"} <= events

    # archive via workflow removes it from answers (§15) — only administrators may archive (§9.4)
    assert client.post(f"/v1/knowledge/{doc_id}/transitions", headers=rep, json={"to": "archived"}).status_code in (403, 404)
    assert client.post(f"/v1/knowledge/{doc_id}/transitions", headers=admin, json={"to": "archived"}).status_code == 200
    after = client.post("/v1/search", headers=rep, json={"question": "can we give 20% discount?"}).json()["results"]
    assert all(x["source"] != "Sales Pricing Policy" for x in after)
