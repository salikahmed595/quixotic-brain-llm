"""quixotic-mcp sidecar (integrations/mcp/server.py): exactly the allowed tools, signatures the API accepts, bearer auth."""
import asyncio
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

pytest.importorskip("mcp")

from backend.api.v1.integrations import sign  # noqa: E402

SERVER = Path(__file__).resolve().parents[1] / "integrations" / "mcp" / "server.py"
SECRET = "s" * 40


def load(monkeypatch, **env):
    for k, v in {"QUIXOTIC_API_URL": "http://api:8000", "QB_HERMES_SHARED_SECRET": SECRET, "QUIXOTIC_MCP_TOKEN": "tok", **env}.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("quixotic_mcp_server", SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_only_the_five_controlled_tools_exist(monkeypatch):           # PRD §15: no shell, files, approvals or publishing
    mod = load(monkeypatch)
    names = {t.name for t in asyncio.run(mod.server.list_tools())}
    assert names == {"get_context", "search_approved_knowledge", "propose_knowledge_change", "get_proposal_status", "report_knowledge_gap"}


def test_calls_are_signed_so_the_api_accepts_them_and_errors_reach_the_agent(monkeypatch):
    mod = load(monkeypatch, QUIXOTIC_DEFAULT_TELEGRAM_USER="111")
    seen = {}

    def handler(request: httpx.Request):
        body = request.content
        ts = request.headers["X-Quixotic-Timestamp"]
        assert request.headers["X-Quixotic-Signature"] == sign(SECRET, ts, body)       # the API's own check
        seen["path"], seen["payload"] = request.url.path, json.loads(body)
        if seen["payload"]["telegram_user_id"] == "999":
            return httpx.Response(403, json={"detail": "This Telegram account is not linked"})
        return httpx.Response(201, json={"proposal_id": "p1", "status": "awaiting_confirmation"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = mod.call("/v1/integrations/hermes/knowledge-proposals", {"telegram_user_id": mod._who(None), "title": "x"}, client)
    assert out["status"] == "awaiting_confirmation" and seen["payload"]["telegram_user_id"] == "111"   # one-person default
    assert mod.call("/v1/integrations/hermes/search", {"telegram_user_id": "999"}, client) == {"error": "This Telegram account is not linked"}


def test_hermes_must_present_the_bearer_token(monkeypatch):
    mod = load(monkeypatch)
    sent = []

    async def inner(scope, receive, send):
        sent.append("inner")

    async def run(headers):
        out = []
        async def send(m): out.append(m)
        await mod.BearerAuth(inner)({"type": "http", "headers": headers}, None, send)
        return out
    denied = asyncio.run(run([]))
    assert denied[0]["status"] == 401 and not sent
    asyncio.run(run([(b"authorization", b"Bearer tok")]))
    assert sent == ["inner"]
