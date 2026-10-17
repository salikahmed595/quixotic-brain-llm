"""Wiring: builds every collaborator once at start-up (PRD §28/§24: providers stay swappable)."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Optional

from ..analytics.dashboard import AnalyticsStore
from ..auth.security import SlidingWindowLimiter
from ..config import Settings
from ..database.accounts import OneTimeTokenStore, SessionStore, SystemSettingsStore
from ..database.conversations import ConversationStore
from ..database.gaps import GapStore
from ..database.integrations import IntegrationStore
from ..database.knowledge import KnowledgeStore
from ..database.ops import OpsStore
from ..database.pool import make_pool, migrate
from ..database.retrieval_store import RetrievalSQLStore
from ..database.users import UserStore
from ..generation.base import get_generator
from ..ingestion.pipeline import IngestionService
from ..learning.feedback import make_signal_source
from ..notifications.mail import make_mailer
from ..ingestion.storage import LocalDirStorage, S3Storage, SQSQueue
from ..reranking.base import get_reranker
from ..retrieval.ask import AskService
from ..retrieval.embeddings import get_embedder
from ..retrieval.language import LanguageService
from ..retrieval.search import SearchService
from ..sales_memory.importer import SalesMemoryImporter


@dataclass
class Services:
    settings: Settings
    users: Any
    knowledge: Any
    ops: Any
    analytics: Any
    search: Any
    ask: Any
    ingestion: Any
    importer: Any
    storage: Any
    queue: Any
    language: LanguageService
    embedder: Any
    limiter: SlidingWindowLimiter
    pool: Any = None
    conversations: Any = None
    models_ready: Any = None            # threading.Event set when the embedding model and reranker are in memory
    sessions: Any = None                # PRD §5 FR-AUTH-06 server-side sessions
    one_time: Any = None                # verification / reset links
    system_settings: Any = None         # PRD §12 system_settings
    mailer: Any = None                  # PRD §5 FR-AUTH-02 email
    gaps: Any = None                    # PRD §9 knowledge gaps
    integrations: Any = None            # PRD §9 / §12 integration identities and events
    approvals_bot: Any = None           # backend-owned Telegram approvals bot (None when Telegram is not configured)


def build_services(settings: Settings, parser=None, extractor=None, run_migrations: bool = True,
                   warm_reranker: bool = True) -> Services:
    """`parser` / `extractor` are the sales-memory plug-ins the PRD leaves undefined (see sales_memory/importer.py)."""
    if run_migrations:
        migrate(settings.database_url)
    pool = make_pool(settings.database_url)
    t = settings.tenant_id
    embedder = get_embedder(settings)
    knowledge, ops = KnowledgeStore(pool, t), OpsStore(pool, t)
    language = LanguageService(settings.roman_urdu_min_ratio, vocab_loader=ops.list_vocabulary)   # + words taught in the app
    store = RetrievalSQLStore(pool, t)
    search = SearchService(store, embedder, get_reranker(settings), language, settings, feedback_signals=make_signal_source(ops, settings))
    storage = LocalDirStorage(settings.raw_storage_dir) if settings.raw_storage_dir else S3Storage(settings)
    reranker = search.reranker
    ready = threading.Event()

    def _warm() -> None:       # loading BGE-M3 + reranker from disk takes 1-2 minutes: do it now, not on the first question
        try:
            for m in ((embedder, reranker) if warm_reranker else (embedder,)):   # the worker never reranks: keep ~2 GB free
                if m is not None and hasattr(m, "warm"):
                    m.warm()
        except Exception:
            logging.getLogger("warmup").exception("model warm-up failed; models will load on first use")
        finally:
            ready.set()
    threading.Thread(target=_warm, daemon=True, name="model-warmup").start()
    out = Services(
        settings=settings, users=UserStore(pool, t), knowledge=knowledge, ops=ops, analytics=AnalyticsStore(pool, t),
        search=search, ask=AskService(search, get_generator(settings), settings),
        ingestion=IngestionService(knowledge, storage, embedder, language, settings),
        importer=SalesMemoryImporter(ops, embedder, language, parser, extractor),
        storage=storage, queue=SQSQueue(settings), language=language, embedder=embedder,
        limiter=SlidingWindowLimiter(), pool=pool, conversations=ConversationStore(pool, t), models_ready=ready,
        sessions=SessionStore(pool, t), one_time=OneTimeTokenStore(pool), system_settings=SystemSettingsStore(pool, t),
        mailer=make_mailer(settings), gaps=GapStore(pool, t), integrations=IntegrationStore(pool, t))
    if settings.telegram_bot_token:
        from ..integrations.approvals_bot import ApprovalsBot
        from ..integrations.telegram import TelegramBot
        out.approvals_bot = ApprovalsBot(out, TelegramBot(settings.telegram_bot_token))
    return out
