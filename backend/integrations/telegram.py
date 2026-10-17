"""Minimal Telegram Bot API client for the backend-owned "Quixotic Approvals" bot (docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md H3).

Only the calls this bot needs: sendMessage with inline buttons, editMessageReplyMarkup, answerCallbackQuery, getUpdates (local
development without a public HTTPS address) and setWebhook. The token stays on the server (PRD §10)."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

log = logging.getLogger("telegram")
API = "https://api.telegram.org"


class TelegramError(RuntimeError):
    pass


class TelegramBot:
    def __init__(self, token: str, timeout: float = 15.0) -> None:
        self._base = f"{API}/bot{token}"
        self._http = httpx.Client(timeout=timeout)

    def _call(self, method: str, **params) -> dict:
        try:
            r = self._http.post(f"{self._base}/{method}", json={k: v for k, v in params.items() if v is not None})
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise TelegramError(f"{method} failed: {type(e).__name__}")         # never log the URL: it contains the token
        if not data.get("ok"):
            raise TelegramError(f"{method} failed: {data.get('description', 'unknown error')}")
        return data["result"]

    def send(self, chat_id: str, text: str, buttons: Optional[list[list[tuple[str, str]]]] = None) -> int:
        """Returns the message id. `buttons` rows of (label, callback data)."""
        markup = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]} if buttons else None
        return self._call("sendMessage", chat_id=chat_id, text=text[:4000], reply_markup=markup, disable_web_page_preview=True)["message_id"]

    def clear_buttons(self, chat_id: str, message_id: int) -> None:
        try:
            self._call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id, reply_markup={"inline_keyboard": []})
        except TelegramError:
            pass                                                   # already edited / too old: harmless

    def answer_callback(self, callback_id: str, text: str) -> None:
        try:
            self._call("answerCallbackQuery", callback_query_id=callback_id, text=text[:190])
        except TelegramError:
            pass

    def get_updates(self, offset: Optional[int], timeout: int = 25) -> list[dict]:
        r = self._http.post(f"{self._base}/getUpdates", json={"offset": offset, "timeout": timeout,
                                                              "allowed_updates": ["message", "callback_query"]}, timeout=timeout + 10)
        data = r.json()
        if not data.get("ok"):
            raise TelegramError(f"getUpdates failed: {data.get('description')}")
        return data["result"]

    def set_webhook(self, url: str, secret: str) -> None:
        self._call("setWebhook", url=url, secret_token=secret, allowed_updates=["message", "callback_query"])
