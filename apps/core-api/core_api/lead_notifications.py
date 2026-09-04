from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import requests

from core_api.config import get_settings
from core_api.models import Lead, LeadSegment, LeadSource, LegalIntake

logger = logging.getLogger(__name__)

_SOURCE_HEADERS: dict[LeadSource, str] = {
    LeadSource.telegram_bot: "🆕 Новая заявка из Telegram-бота",
    LeadSource.website_form: "🆕 Новая заявка с сайта",
    LeadSource.telegram_channel: "🆕 Новая заявка из Telegram-канала",
    LeadSource.miniapp_form: "🆕 Новая заявка из Mini App",
}

_SEGMENT_LABELS: dict[LeadSegment, str] = {
    LeadSegment.inhouse: "Юр. отдел компании",
    LeadSegment.law_firm: "Юридическая фирма",
    LeadSegment.entrepreneur: "Предприниматель",
    LeadSegment.other: "Не указан",
}

_OFFER_LABELS: dict[str, str] = {
    "consultation": "Бесплатная консультация",
    "checklist": "Гайд по внедрению ИИ",
    "demo": "Демонстрационный разбор договора",
    "sample_report": "Пример отчёта по договору",
    "unknown": "Общий запрос",
}

_AUDIENCE_LABELS: dict[str, str] = {
    "lawyer": "Юрист",
    "business": "Бизнес",
    "mixed": "Смешанная",
}

_LEGAL_CLIENT_LABELS = {
    "company": "Компания",
    "entrepreneur": "Предприниматель",
    "individual": "Частное лицо",
    "unknown": "Не указан",
}

_LEGAL_AREA_LABELS = {
    "contracts": "Договоры и сделки",
    "disputes": "Претензии и споры",
    "corporate": "Корпоративные вопросы",
    "employment": "Трудовые отношения",
    "tax_compliance": "Налоги и комплаенс",
    "real_estate": "Недвижимость и земля",
    "it_ip_data": "IT, интеллектуальная собственность и данные",
    "family_inheritance": "Семейные и наследственные вопросы",
    "debt_bankruptcy": "Долги и банкротство",
    "other": "Другая юридическая задача",
}

_LEGAL_URGENCY_LABELS = {
    "urgent": "Срок сегодня или завтра",
    "high": "Срок до трёх дней",
    "normal": "Срок позднее",
    "no_deadline": "Срок не указан",
}

# Тех-флаги внутри notes, которые менеджеру показывать не нужно.
_NOTES_TECHNICAL_KEYS = frozenset(
    {"ip_hash", "ua_hash", "security_flags", "telegram_verified"}
)

_DISPLAY_TZ = ZoneInfo("Europe/Moscow")


def _parse_notes(notes: str | None) -> tuple[dict[str, str], str | None]:
    """Split notes into structured key=value pairs and a free-text message.

    Lines that look like `key=value` are returned in the dict (excluding
    technical keys). Everything else is concatenated into the free-text
    message. We also pull the `message=...` value out of the dict and
    return it as the message.
    """
    if not notes:
        return {}, None

    parsed: dict[str, str] = {}
    free_lines: list[str] = []
    for raw_line in notes.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key in _NOTES_TECHNICAL_KEYS:
                continue
            if key == "message":
                free_lines.append(value)
                continue
            if key:
                parsed[key] = value
                continue
        free_lines.append(line)

    message = "\n".join(free_lines).strip() or None
    return parsed, message


def _format_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    local = value.astimezone(_DISPLAY_TZ)
    return local.strftime("%d.%m.%Y %H:%M (Мск)")


def _format_lead_message(lead: Lead) -> str:
    header = _SOURCE_HEADERS.get(lead.source, "🆕 Новая заявка")
    parsed_notes, message = _parse_notes(lead.notes)

    lines: list[str] = [header, ""]

    if lead.name:
        lines.append(f"👤 Имя: {lead.name}")
    if lead.contact:
        lines.append(f"📞 Контакт: {lead.contact}")

    segment_label: str | None = None
    if lead.segment is not None:
        segment_label = _SEGMENT_LABELS.get(lead.segment)
    if segment_label and segment_label != _SEGMENT_LABELS[LeadSegment.other]:
        lines.append(f"💼 Сегмент: {segment_label}")

    offer_key = parsed_notes.get("offer")
    if offer_key:
        offer_label = _OFFER_LABELS.get(offer_key, offer_key)
        lines.append(f"🎯 Запрос: {offer_label}")

    if lead.source == LeadSource.miniapp_form:
        audience = parsed_notes.get("audience")
        if audience:
            lines.append(f"🎓 Аудитория: {_AUDIENCE_LABELS.get(audience, audience)}")
        goal = parsed_notes.get("goal")
        if goal:
            lines.append(f"🧭 Цель: {goal}")
        if lead.telegram_user_id:
            lines.append(f"💬 Telegram ID: {lead.telegram_user_id}")

    if message:
        lines.append("")
        lines.append("💬 Сообщение:")
        snippet = message[:1000]
        lines.append(snippet)

    landing = parsed_notes.get("landing")
    if landing:
        lines.append("")
        lines.append(f"📍 Страница: {landing}")

    if lead.utm_source:
        utm_bits = [lead.utm_source]
        if lead.utm_medium:
            utm_bits.append(lead.utm_medium)
        if lead.utm_campaign:
            utm_bits.append(lead.utm_campaign)
        lines.append(f"🌐 Источник трафика: {' / '.join(utm_bits)}")

    timestamp = _format_timestamp(lead.created_at or lead.last_activity_at)
    if timestamp:
        lines.append("")
        lines.append(f"⏰ {timestamp}")

    return "\n".join(lines).strip()


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
    from sqlalchemy import select

    from core_api.db import SessionLocal

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
        text = _format_lead_message(lead)
    finally:
        db.close()

    try:
        _post_telegram_message(token, chat_id, text)
    except Exception:
        logger.exception("Failed to send new-lead Telegram notification", extra={"lead_id": str(lead_id)})



def _legal_intake_analysis_block(intake: dict[str, object]) -> str:
    """Готовит блок с разбором обращения для сообщения юристу.

    Возвращает пустую строку, если разбор выключен, не настроен или не удался:
    уведомление в этом случае уходит без аналитики.
    """
    from core_api.intake_analysis import analyze_intake, format_cost

    settings = get_settings()
    if not settings.intake_analysis_enabled or not settings.intake_analysis_api_key:
        return ""

    result = analyze_intake(
        intake,
        api_key=settings.intake_analysis_api_key,
        base_url=settings.intake_analysis_base_url,
        model=settings.intake_analysis_model,
        proxy_url=settings.intake_analysis_proxy_url or None,
        timeout=settings.intake_analysis_timeout_seconds,
    )

    if not result.ok:
        logger.warning("legal_intake_analysis_skipped", extra={"error": result.error})
        return ""

    return "\n".join(
        [
            "",
            "— — —",
            "РАЗБОР",
            "",
            result.text,
            "",
            f"Модель: {result.model}",
            f"Стоимость: {format_cost(result.cost_usd)} "
            f"(вход {result.prompt_tokens} · выход {result.completion_tokens})",
        ]
    )

def notify_new_legal_intake(intake_id: uuid.UUID) -> None:
    """Notify the manager about a legal-help intake without attaching documents."""
    from sqlalchemy import select

    from core_api.db import SessionLocal

    settings = get_settings()
    token = settings.lead_notify_bot_token
    chat_id = settings.lead_notify_chat_id
    if not token or not chat_id:
        logger.debug("Legal intake notify not configured", extra={"intake_id": str(intake_id)})
        return

    db = SessionLocal()
    try:
        row = db.execute(
            select(LegalIntake, Lead)
            .join(Lead, Lead.id == LegalIntake.lead_id)
            .where(LegalIntake.id == intake_id)
        ).one_or_none()
        if row is None:
            logger.warning("Legal intake %s vanished before notify", intake_id)
            return
        item, lead = row
        header = "СРОЧНОЕ ЮРИДИЧЕСКОЕ ОБРАЩЕНИЕ" if item.urgency.value == "urgent" else "НОВОЕ ЮРИДИЧЕСКОЕ ОБРАЩЕНИЕ"
        lines = [
            header,
            "",
            f"Клиент: {_LEGAL_CLIENT_LABELS[item.client_type.value]}",
            f"Направление: {_LEGAL_AREA_LABELS[item.legal_area.value]}",
            f"Срочность: {_LEGAL_URGENCY_LABELS[item.urgency.value]}",
            f"Контакт: {lead.contact or 'не указан'}",
        ]
        if lead.name:
            lines.append(f"Имя: {lead.name}")
        if lead.company:
            lines.append(f"Организация: {lead.company}")
        if item.region:
            lines.append(f"Регион: {item.region}")
        if item.deadline:
            lines.append(f"Ближайший срок: {item.deadline}")
        lines.extend(["", "Краткое описание:", item.description[:600]])
        intake_payload = {
            "description": item.description,
            "client_type": _LEGAL_CLIENT_LABELS[item.client_type.value],
            "legal_area": _LEGAL_AREA_LABELS[item.legal_area.value],
            "urgency": _LEGAL_URGENCY_LABELS[item.urgency.value],
            "deadline": item.deadline,
            "region": item.region,
        }
        lines.append(f"\nID: {item.id}")
        text = "\n".join(lines)
    finally:
        db.close()

    # Разбор — дополнение к уведомлению, а не условие его отправки: сбой модели
    # или недоступность вендора не должны задерживать сообщение о клиенте.
    analysis_block = _legal_intake_analysis_block(intake_payload)
    if analysis_block:
        text = f"{text}\n{analysis_block}"

    try:
        _post_telegram_message(token, chat_id, text)
    except Exception:
        logger.exception(
            "Failed to send legal-intake Telegram notification",
            extra={"intake_id": str(intake_id)},
        )
