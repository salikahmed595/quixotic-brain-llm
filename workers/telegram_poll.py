"""Approvals bot without a public HTTPS address (local development): long-polls Telegram instead of the webhook.
Production uses the webhook (POST /v1/integrations/telegram/webhook behind the HTTPS proxy; `python -m backend.cli telegram-webhook`).
A bot can use only one of the two at a time. Run: python -m workers.telegram_poll"""
from __future__ import annotations

import logging
import time

from backend.api.services import build_services
from backend.config import get_settings

log = logging.getLogger("telegram_poll")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    svc = build_services(get_settings(), warm_reranker=False)
    if svc.approvals_bot is None:
        raise SystemExit("QB_TELEGRAM_BOT_TOKEN is not set")
    bot, offset = svc.approvals_bot.bot, None
    log.info("polling Telegram for the approvals bot")
    while True:
        try:
            for update in bot.get_updates(offset):
                offset = update["update_id"] + 1
                try:
                    svc.approvals_bot.handle_update(update)
                except Exception:
                    log.exception("update %s failed", update.get("update_id"))
        except Exception:
            log.exception("polling failed; retrying in 5 s")
            time.sleep(5)


if __name__ == "__main__":
    main()
