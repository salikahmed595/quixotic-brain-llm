"""FastAPI application (PRD §49). Run: uvicorn backend.main:app"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.services import Services, build_services
from .api.v1 import admin, ask, auth, chats, conversations, feedback, gaps, insights, knowledge, sales, system, vocabulary
from .config import get_settings


def create_app(services: Optional[Services] = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if services is None:                 # tests inject fakes; production builds the real collaborators here
            app.state.services = build_services(get_settings())
        yield

    app = FastAPI(title="Quixotic Brain", version="v1", lifespan=lifespan)
    if services is not None:
        app.state.services = services
    for r in (insights.router, auth.router, admin.public, ask.router, knowledge.router, knowledge.admin, gaps.router, system.router, sales.router,
              feedback.router, admin.router, chats.router, conversations.router, vocabulary.router):
        app.include_router(r)
    # Optional, for hosting the front-end elsewhere (stack: Vercel). Comma-separated origins; unset = no CORS.
    origins = [o.strip() for o in os.environ.get("QB_CORS_ORIGINS", "").split(",") if o.strip()]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
    # Optional, for local use: serve the static front-end from the API (same origin, no CORS needed).
    frontend = os.environ.get("QB_FRONTEND_DIR")
    if frontend and Path(frontend).is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
