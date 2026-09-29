"""
Handlers for /start payload entrypoints and referral bridges.
"""
from __future__ import annotations

import html
import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Dict

import content
import database
import utils
from config import get_config
from .helpers import notify_admin_new_lead
from .markup import consultation_contact_markup

logger = logging.getLogger(__name__)
config = get_config()

_READER_START_PAYLOAD_RE = re.compile(r"^readerq_(?P<post_id>[0-9a-fA-F-]{36})$")
# Кнопка «Ассистент AI Verdict» прямо под постом в канале (news/publish.py).
_CHANNEL_START_PAYLOAD_RE = re.compile(r"^chq_(?P<post_id>[0-9a-fA-F-]{36})$")
# Пост, из которого человек пришёл: ассистент отвечает с опорой на него.
CHANNEL_POST_CONTEXT_KEY = "channel_post_context"
CHANNEL_POST_CONTEXT_TTL_SECONDS = 24 * 3600
CHANNEL_POST_EVENT = "channel_post_start"
_CONTRACT_START_PAYLOAD_RE = re.compile(
    r"^contract_(?P<entry>demo|checklist|sample_report|consultation|cabinet)$"
)
PENDING_START_PAYLOAD_KEY = "pending_start_payload"
LEGAL_HELP_START_PAYLOAD = "legal_help"


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
    origin: str = "reader",
) -> Dict:
    """Лид по посту. origin — откуда пришёл: из бота-читателя или прямо из
    канала; метки разные, чтобы статистика читателя не смешивалась с каналом."""
    title = (post_context.get("title") or "").strip()
    source_url = (post_context.get("source_url") or "").strip()
    rubric = (post_context.get("rubric") or "").strip()
    from_channel = origin == "channel"
    notes_parts = ["[CHANNEL_POST]" if from_channel else "[READER_REFERRAL]", f"post_id={post_id}"]
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
        "name": user_first_name or ("Клиент из канала" if from_channel else "Клиент из Reader"),
        "pain_point": pain_point,
        "temperature": "warm",
        "status": "new",
        "service_category": "ai_legal_consulting",
        "specific_need": "Разбор публикации и план внедрения",
        "lead_magnet_type": "consultation",
        "lead_magnet_delivered": 0,
        "notification_sent": 0,
        "conversation_stage": "qualify",
        "cta_variant": "channel_post" if from_channel else "reader_referral",
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
    origin: str = "reader",
) -> bool:
    post_context = fetch_post_context(post_id)
    lead_payload = build_reader_referral_lead_payload(
        user_first_name=user.first_name or "",
        post_id=post_id,
        post_context=post_context,
        origin=origin,
    )

    lead_id = database.db.create_new_lead(user_data["id"], lead_payload)
    database.db.track_event(
        user_data["id"],
        "channel_post_start" if origin == "channel" else "reader_referral_start",
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
    head = (
        "✅ Вы пришли из поста в канале — заявка создана.\n\n"
        if origin == "channel"
        else "✅ Переход из ридер-бота принят, заявка создана.\n\n"
    )
    await utils.safe_reply_text(
        message,
        (
            f"{head}"
            f"{title_block}"
            "Можете сразу описать ваш вопрос по внедрению в 1-2 предложениях "
            "или отправить телефон кнопкой ниже."
        ),
        reply_markup=consultation_contact_markup(),
        action="channel_post_start" if origin == "channel" else "reader_referral_start",
    )
    return True


def _plain_excerpt(text: str, limit: int = 1500) -> str:
    """Текст поста без разметки — для контекста ассистента."""
    plain = re.sub(r"<[^>]+>", " ", text or "")
    plain = " ".join(html.unescape(plain).split())
    return plain[:limit].rstrip() + ("…" if len(plain) > limit else "")


def channel_post_greeting(title: str) -> str:
    about = f" «{title}»" if title else ""
    return (
        f"Здравствуйте! Я Ассистент AI Verdict. Вы пришли из поста{about}.\n\n"
        "Спросите, что важно именно вам: как это касается вашей ситуации или бизнеса, "
        "что делать дальше, как применить или автоматизировать похожее у себя. Отвечу с учётом "
        "материала, а если понадобится юрист или разработчик — передам ему вашу задачу."
    )


async def handle_channel_post_start(
    *,
    message,
    context,
    user_data: Dict,
    user,
    post_id: str,
) -> bool:
    """Кнопка под постом в канале — разговор с Ассистентом по этому посту.

    Платформа многопрофильная: по посту спрашивают и о праве, и об
    автоматизации, поэтому здесь не приём заявки к юристу, а тот же умный
    ассистент (RAG, память темы, контекст дел), что и в обычном диалоге, —
    только он знает, какой пост человек читал. Заявка появится, когда
    человек сам оставит контакт; метку «из канала» ей проставит квалификация
    (lead_qualifier) по событию channel_post_start.
    """
    post = fetch_post_context(post_id)
    title = (post.get("title") or "").strip()
    database.db.track_event(
        user_data["id"],
        CHANNEL_POST_EVENT,
        payload={"post_id": post_id, "post_title": title, "rubric": post.get("rubric") or ""},
    )
    if context is not None and isinstance(getattr(context, "user_data", None), dict):
        context.user_data[CHANNEL_POST_CONTEXT_KEY] = {
            "post_id": post_id,
            "title": title,
            "rubric": (post.get("rubric") or "").strip(),
            "source_url": (post.get("source_url") or "").strip(),
            "excerpt": _plain_excerpt(post.get("text") or ""),
            "at": time.time(),
        }
    greeting = channel_post_greeting(title)
    # Приветствие — в историю диалога: модель видит, с чего начался разговор.
    database.db.add_message(user_data["id"], "assistant", greeting)
    await utils.safe_reply_text(message, greeting, action=CHANNEL_POST_EVENT)
    return True


def channel_post_context_block(user_store: Dict | None, now: float | None = None) -> str:
    """Блок контекста для ассистента: из какого поста пришёл собеседник (сутки после перехода)."""
    post = (user_store or {}).get(CHANNEL_POST_CONTEXT_KEY)
    if not isinstance(post, dict):
        return ""
    if (now or time.time()) - float(post.get("at") or 0) > CHANNEL_POST_CONTEXT_TTL_SECONDS:
        return ""
    lines = ["Собеседник пришёл из поста в Telegram-канале AI Verdict."]
    if post.get("title"):
        lines.append(f"Заголовок поста: {post['title']}")
    if post.get("rubric"):
        lines.append(f"Рубрика: {post['rubric']}")
    if post.get("excerpt"):
        lines.append(f"Текст поста (фрагмент): {post['excerpt']}")
    lines.append(
        "Если вопрос связан с постом — отвечай с опорой на него и на знания платформы, "
        "не пересказывай пост целиком. Помни, что платформа многопрофильная: право, "
        "автоматизация и их сочетание."
    )
    return "\n".join(lines)


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

    channel_match = _CHANNEL_START_PAYLOAD_RE.match(payload)
    if channel_match:
        return await handle_channel_post_start(
            message=message,
            context=context,
            user_data=user_data,
            user=user,
            post_id=channel_match.group("post_id"),
        )

    match = _READER_START_PAYLOAD_RE.match(payload)
    if not match:
        from .case_messages import CASE_START_PAYLOAD_RE, handle_case_start_payload

        case_match = CASE_START_PAYLOAD_RE.match(payload)
        if case_match:
            return await handle_case_start_payload(
                message=message,
                context=context,
                user=user,
                intake_id=case_match.group("intake_id"),
            )
        from .client_link import LINK_START_PAYLOAD, send_link_code

        if payload == LINK_START_PAYLOAD:
            return await send_link_code(message, user)
        if payload == LEGAL_HELP_START_PAYLOAD:
            from .legal_help import prompt_legal_help_client_type

            await prompt_legal_help_client_type(message, context)
            return True
        if payload in {"engineering_help", "hybrid_help"}:
            from .engineering_help import prompt_category

            await prompt_category(
                message, context, "engineering" if payload == "engineering_help" else "hybrid"
            )
            return True
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
