from __future__ import annotations

import logging

import requests

from core_api.config import get_settings

logger = logging.getLogger(__name__)


def send_telegram_alert(text: str) -> None:
    settings = get_settings()
    if not settings.alert_bot_token or not settings.alert_chat_id:
        return

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{settings.alert_bot_token}/sendMessage",
            data={"chat_id": settings.alert_chat_id, "text": text},
            timeout=5,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to send Telegram alert")
