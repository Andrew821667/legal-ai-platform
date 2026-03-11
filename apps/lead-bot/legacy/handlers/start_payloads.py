"""
Handlers for /start payload entrypoints and referral bridges.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Dict

import content
import database
import utils
from config import get_config
from handlers.helpers import notify_admin_new_lead
from handlers.markup import consultation_contact_markup

logger = logging.getLogger(__name__)
config = get_config()

_READER_START_PAYLOAD_RE = re.compile(r"^readerq_(?P<post_id>[0-9a-fA-F-]{36})$")
_CONTRACT_START_PAYLOAD_RE = re.compile(
    r"^contract_(?P<entry>demo|checklist|sample_report|consultation|cabinet)$"
)
PENDING_START_PAYLOAD_KEY = "pending_start_payload"


def news_api_key() -> str:
    return (config.API_KEY_NEWS or config.API_KEY_ADMIN or config.API_KEY_BOT or "").strip()


def fetch_post_context(post_id: str) -> Dict[str, str]:
    base_url = (config.CORE_API_URL or "").rstrip("/")
    api_key = news_api_key()
    if not base_url or not api_key:
        return {}

    request = urllib.request.Request(
        url=f"{base_url}/api/v1/scheduled-posts/{post_id}",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.CORE_API_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            payload = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        logger.warning("reader referral post fetch failed (%s): %s", error.code, post_id)
        return {}
    except Exception as error:
        logger.warning("reader referral post fetch error for %s: %s", post_id, error)
        return {}

    return {
        "title": str(payload.get("title") or "").strip(),
        "text": str(payload.get("text") or "").strip(),
        "source_url": str(payload.get("source_url") or "").strip(),
        "rubric": str(payload.get("rubric") or "").strip(),
        "format_type": str(payload.get("format_type") or "").strip(),
    }


def build_reader_referral_lead_payload(
    *,
    user_first_name: str,
    post_id: str,
    post_context: Dict[str, str],
) -> Dict:
    title = (post_context.get("title") or "").strip()
    source_url = (post_context.get("source_url") or "").strip()
    rubric = (post_context.get("rubric") or "").strip()
    notes_parts = ["[READER_REFERRAL]", f"post_id={post_id}"]
    if title:
        notes_parts.append(f"title={title}")
    if source_url:
        notes_parts.append(f"source_url={source_url}")
    if rubric:
        notes_parts.append(f"rubric={rubric}")

    pain_point = (
        f"Нужно разобрать материал «{title}» и понять, как применить в юрфункции."
        if title
        else "Нужно разобрать материал из канала и применить в юридической работе."
    )
    return {
        "name": user_first_name or "Клиент из Reader",
        "pain_point": pain_point,
        "temperature": "warm",
        "status": "new",
        "service_category": "ai_legal_consulting",
        "specific_need": "Разбор публикации и план внедрения",
        "lead_magnet_type": "consultation",
        "lead_magnet_delivered": 0,
        "notification_sent": 0,
        "conversation_stage": "qualify",
        "cta_variant": "reader_referral",
        "cta_shown": 1,
        "notes": "\n".join(notes_parts)[:3500],
    }


async def handle_reader_referral_start(
    *,
    message,
    context,
    user_data: Dict,
    user,
    post_id: str,
) -> bool:
    post_context = fetch_post_context(post_id)
    lead_payload = build_reader_referral_lead_payload(
        user_first_name=user.first_name or "",
        post_id=post_id,
        post_context=post_context,
    )

    lead_id = database.db.create_new_lead(user_data["id"], lead_payload)
    database.db.track_event(
        user_data["id"],
        "reader_referral_start",
        payload={
            "post_id": post_id,
            "post_title": post_context.get("title") or "",
            "source_url": post_context.get("source_url") or "",
        },
        lead_id=lead_id,
    )
    await notify_admin_new_lead(
        context,
        lead_id,
        lead_payload,
        user_data,
        is_update=False,
    )

    title = (post_context.get("title") or "").strip()
    title_block = f"Материал: {title}\n\n" if title else ""
    await utils.safe_reply_text(
        message,
        (
            "✅ Переход из ридер-бота принят, заявка создана.\n\n"
            f"{title_block}"
            "Можете сразу описать ваш вопрос по внедрению в 1-2 предложениях "
            "или отправить телефон кнопкой ниже."
        ),
        reply_markup=consultation_contact_markup(),
        action="reader_referral_start",
    )
    return True


def contract_payload_magnet(entry: str) -> str:
    mapping = {
        "demo": "demo",
        "checklist": "checklist",
        "sample_report": "sample_report",
        "consultation": "consultation",
        "cabinet": "consultation",
    }
    return mapping.get(entry, "consultation")


async def handle_contract_start_payload(
    *,
    message,
    context,
    user_data: Dict,
    user,
    payload: str,
) -> bool:
    match = _CONTRACT_START_PAYLOAD_RE.match(payload)
    if not match:
        return False

    entry = match.group("entry")
    magnet_type = contract_payload_magnet(entry)
    previous_lead = database.db.get_lead_by_user_id(user_data["id"]) or {}
    is_update = bool(previous_lead)
    notes = (previous_lead.get("notes") or "").strip()
    marker = f"[CONTRACT_ENTRY] start={payload}"
    notes = f"{notes}\n{marker}".strip() if notes else marker
    lead_payload = {
        "name": previous_lead.get("name") or user.first_name,
        "email": previous_lead.get("email"),
        "phone": previous_lead.get("phone"),
        "company": previous_lead.get("company"),
        "pain_point": previous_lead.get("pain_point")
        or "Интерес к модулю проверки договоров и автоматизации договорной работы.",
        "temperature": "warm",
        "status": "new",
        "notification_sent": 0,
        "lead_magnet_type": magnet_type,
        "lead_magnet_delivered": 0,
        "service_category": previous_lead.get("service_category") or "contract_automation",
        "specific_need": previous_lead.get("specific_need") or "Contract AI",
        "notes": notes,
    }
    lead_id = database.db.create_or_update_lead(user_data["id"], lead_payload)
    lead_snapshot = database.db.get_lead_by_id(lead_id) or lead_payload
    await notify_admin_new_lead(
        context=context,
        lead_id=lead_id,
        lead_data=lead_snapshot,
        user_data=user_data,
        is_update=is_update,
    )

    if entry == "cabinet":
        await utils.safe_reply_text(
            message,
            (
                "🖥 Запрос на доступ к модулю Contract_AI_System принят.\n\n"
                "Это отдельный сервис для проверки договоров. "
                "Оставьте контакт, и мы согласуем следующий шаг и формат доступа."
            ),
            reply_markup=consultation_contact_markup(),
            action="contract_start_cabinet",
        )
        return True

    selection_text = content.LEAD_MAGNET_SELECTION_MESSAGES.get(magnet_type, "Спасибо! Продолжаем.")
    if entry == "demo":
        selection_text = (
            f"{selection_text}\n\n"
            "Можно сразу отправить договор (файл/фото), затем укажите email."
        )
    reply_markup = consultation_contact_markup() if magnet_type == "consultation" else None
    await utils.safe_reply_text(
        message,
        selection_text,
        reply_markup=reply_markup,
        action=f"contract_start_{entry}",
    )
    return True


async def process_pending_start_payload(
    *,
    message,
    context,
    user_data: Dict,
    user,
) -> bool:
    payload = str((context.user_data or {}).pop(PENDING_START_PAYLOAD_KEY, "") or "").strip()
    if not payload:
        return False

    match = _READER_START_PAYLOAD_RE.match(payload)
    if not match:
        return await handle_contract_start_payload(
            message=message,
            context=context,
            user_data=user_data,
            user=user,
            payload=payload,
        )

    return await handle_reader_referral_start(
        message=message,
        context=context,
        user_data=user_data,
        user=user,
        post_id=match.group("post_id"),
    )
