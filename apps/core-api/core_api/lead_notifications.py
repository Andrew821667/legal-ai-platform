from __future__ import annotations

import logging
import uuid

import requests

from core_api.config import get_settings
from core_api.models import Lead, LeadSource

logger = logging.getLogger(__name__)

_SOURCE_LABELS: dict[LeadSource, str] = {
    LeadSource.telegram_bot: "Telegram bot",
    LeadSource.website_form: "Сайт",
    LeadSource.telegram_channel: "Telegram channel",
    LeadSource.miniapp_form: "Mini App",
}


def _format_lead_message(lead: Lead, web_base_url: str) -> str:
    source_label = _SOURCE_LABELS.get(lead.source, str(lead.source))

    lines: list[str] = [
        "🆕 Новая заявка",
        f"Источник: {source_label}",
    ]
    if lead.name:
        lines.append(f"Имя: {lead.name}")
    if lead.contact:
        lines.append(f"Контакт: {lead.contact}")
    if lead.telegram_user_id:
        lines.append(f"Telegram ID: {lead.telegram_user_id}")
    if lead.segment:
        lines.append(f"Сегмент: {lead.segment.value if hasattr(lead.segment, 'value') else lead.segment}")
    if lead.utm_source or lead.utm_campaign:
        utm_parts = [
            f"utm_source={lead.utm_source}" if lead.utm_source else None,
            f"utm_medium={lead.utm_medium}" if lead.utm_medium else None,
            f"utm_campaign={lead.utm_campaign}" if lead.utm_campaign else None,
        ]
        lines.append("UTM: " + ", ".join(p for p in utm_parts if p))
    if lead.notes:
        snippet = lead.notes[:500]
        lines.append(f"Notes:\n{snippet}")
    lines.append(f"ID: {lead.id}")
    base_url = web_base_url.rstrip("/")
    if base_url:
        lines.append(f"Открыть: {base_url}/admin/leads/{lead.id}")
    return "\n".join(lines)


_NOTIFY_HTTP_TIMEOUT_SECONDS = 15
_NOTIFY_MAX_ATTEMPTS = 3
_NOTIFY_RETRY_BACKOFF_SECONDS = 2


def _post_telegram_message(token: str, chat_id: str, text: str) -> None:
    """POST to Telegram sendMessage with a few retries on transient errors.

    Telegram via VPN/WARP occasionally takes 5–10s for the TLS handshake,
    so we use a generous timeout and retry on timeout/connection errors.
    """
    import time

    last_exc: Exception | None = None
    for attempt in range(1, _NOTIFY_MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": "true",
                },
                timeout=_NOTIFY_HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if attempt < _NOTIFY_MAX_ATTEMPTS:
                time.sleep(_NOTIFY_RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise
        except Exception:
            raise
    if last_exc is not None:
        raise last_exc


def notify_new_lead(lead_id: uuid.UUID) -> None:
    """Send a Telegram message about a newly created lead.

    Best-effort: any failure is logged and swallowed so it never affects
    the request that created the lead.
    """
    from core_api.db import SessionLocal
    from sqlalchemy import select

    settings = get_settings()
    token = settings.lead_notify_bot_token
    chat_id = settings.lead_notify_chat_id
    if not token or not chat_id:
        logger.debug("Lead notify not configured, skip", extra={"lead_id": str(lead_id)})
        return

    db = SessionLocal()
    try:
        lead = db.execute(select(Lead).where(Lead.id == lead_id)).scalar_one_or_none()
        if lead is None:
            logger.warning("Lead %s vanished before notify", lead_id)
            return
        text = _format_lead_message(lead, settings.lead_notify_web_base_url)
    finally:
        db.close()

    try:
        _post_telegram_message(token, chat_id, text)
    except Exception:
        logger.exception("Failed to send new-lead Telegram notification", extra={"lead_id": str(lead_id)})
