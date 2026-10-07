"""Integration fixtures: a REAL PostgreSQL + pgvector database (set QB_TEST_DATABASE_URL, e.g. the docker container).
A throw-away database is created for the run. Embeddings are a deterministic hashing stand-in so the SQL and pipeline are
exercised without loading models; real-model checks live in tests/integration/test_models.py."""
import hashlib
import math
import os
import re
import uuid

import psycopg
import pytest

from backend.analytics.dashboard import AnalyticsStore
from backend.database.knowledge import KnowledgeStore
from backend.database.ops import OpsStore
from backend.database.pool import make_pool, migrate
from backend.database.retrieval_store import RetrievalSQLStore
from backend.database.users import UserStore

ADMIN_URL = os.environ.get("QB_TEST_DATABASE_URL")


class HashEmbedder:
    """1024-d bag-of-words hashing vectors: lexically similar texts are close. Test double, not a product component."""
    name, dim = "test-hash-1024", 1024

    def embed(self, text):
        v = [0.0] * self.dim
        for w in re.findall(r"\w+", text.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_many(self, texts):
        return [self.embed(t) for t in texts]


class MemStorage:
    def __init__(self):
        self.objects = {}

    def put(self, k, d):
        self.objects[k] = d

    def get(self, k):
        return self.objects[k]

    def delete(self, k):
        self.objects.pop(k, None)


@pytest.fixture
def db():   # a fresh database per test: no state leaks between tests
    if not ADMIN_URL:
        pytest.skip("QB_TEST_DATABASE_URL not set")
    name = "qb_test_" + uuid.uuid4().hex[:8]
    base = ADMIN_URL.rsplit("/", 1)[0]
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    url = f"{base}/{name}"
    migrate(url)
    pool = make_pool(url)
    yield pool
    pool.close()
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture
def stores(db):
    t = "quixotic"
    return dict(users=UserStore(db, t), knowledge=KnowledgeStore(db, t), ops=OpsStore(db, t),
                retrieval=RetrievalSQLStore(db, t), analytics=AnalyticsStore(db, t), pool=db)
