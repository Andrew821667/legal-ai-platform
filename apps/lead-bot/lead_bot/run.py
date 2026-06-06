from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from lead_bot.buffer import LeadBuffer
from lead_bot.core_client import CoreClient
from lead_bot.logging_config import setup_logging
from lead_bot.settings import settings

setup_logging()
logger = logging.getLogger(__name__)

core_client = CoreClient(base_url=settings.core_api_url, api_key=settings.api_key_bot)
buffer = LeadBuffer(settings.buffer_db_path)


# Keep these descriptions in sync with apps/web/lib/platformParts.ts.
# The web file is the canonical source for the site-facing UI; this list is
# what /start shows inside Telegram, so the bot reads the same five parts.
_PLATFORM_INTRO = (
    "👋 Это ассистент платформы <b>AI Verdict</b>.\n\n"
    "<b>AI Verdict</b> — это не отдельный бот, а полноценная платформа для "
    "юридической AI-работы. Можно начинать с любого элемента: проверить договор, "
    "прочитать разбор, открыть Mini App или сразу описать задачу здесь.\n\n"
    "Все части связаны между собой — данные, заявки и контекст не теряются:"
)
_PLATFORM_PART_LINES = [
    "🌐 <b>Сайт</b> — продукты, услуги, методология и заявка на консультацию",
    "📄 <b>Contract AI</b> — проверка договоров, риски и рекомендации по правкам",
    "💬 <b>Ассистент</b> — вопросы, демо, заявки и маршрут внедрения",
    "📰 <b>Новостной контур</b> — канал и reader-бот с разборами AI в legal",
    "📱 <b>Mini App</b> — персональный контур: контент, инструменты, профиль и заявка",
]
_CONSENT_VERSION = "telegram_bot_pdn_v1"
_CONSENT_ACCEPT_CALLBACK = "consent_pdn_yes"
_CONSENT_DECLINE_CALLBACK = "consent_pdn_no"


def _consent_text() -> str:
    return (
        "🔐 <b>Сначала — контроль ваших данных</b>\n\n"
        "Для заявки и ответа нужны Telegram ID, имя, username и текст обращения. "
        "Данные используются только для обработки запроса и связи с вами.\n\n"
        "Выберите действие:"
    )


def _consent_keyboard() -> InlineKeyboardMarkup:
    site_url = settings.public_site_url.rstrip("/") or "https://ai-verdict.ru"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Разрешить и продолжить", callback_data=_CONSENT_ACCEPT_CALLBACK)],
            [InlineKeyboardButton("📄 Открыть политику ПД", url=f"{site_url}/privacy")],
            [InlineKeyboardButton("Не передавать данные", callback_data=_CONSENT_DECLINE_CALLBACK)],
        ]
    )


def _platform_map_text() -> str:
    body = "\n".join(_PLATFORM_PART_LINES)
    return f"{_PLATFORM_INTRO}\n\n{body}"


def _platform_map_keyboard() -> InlineKeyboardMarkup:
    site_url = settings.public_site_url.rstrip("/")
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("🌐 Открыть сайт", url=site_url or "https://ai-verdict.ru")],
        [InlineKeyboardButton("📄 Contract AI", url=settings.contract_ai_url)],
        [
            InlineKeyboardButton(
                "📰 Канал",
                url=f"https://t.me/{settings.public_channel_username.lstrip('@')}",
            ),
            InlineKeyboardButton(
                "📰 Reader-бот",
                url=f"https://t.me/{settings.public_reader_bot_username.lstrip('@')}",
            ),
        ],
    ]

    # Mini App entry — prefer the in-Telegram WebApp button if a registered
    # Mini App name is configured (PUBLIC_SELF_MINIAPP_NAME). Otherwise fall
    # back to opening the lead-form page on the site, which works without
    # @BotFather Mini App registration.
    if settings.public_self_miniapp_name:
        miniapp_url = (
            f"{site_url or 'https://ai-verdict.ru'}/miniapp"
        )
        rows.append([InlineKeyboardButton("📱 Открыть Mini App", web_app=WebAppInfo(url=miniapp_url))])
    elif site_url:
        rows.append([InlineKeyboardButton("📱 Mini App на сайте", url=f"{site_url}/miniapp")])

    return InlineKeyboardMarkup(rows)


def _flush_buffer_once() -> None:
    items = buffer.fetch_oldest()
    for item in items:
        try:
            resp = core_client.post_lead(item.payload, idempotency_key=item.idempotency_key)
            if resp.status_code in (200, 201):
                buffer.delete(item.row_id)
                time.sleep(0.1)
                continue
            if resp.status_code >= 500:
                logger.warning("Core unavailable, stop flush", extra={"status": resp.status_code})
                break
            logger.warning("Drop invalid buffered lead", extra={"status": resp.status_code, "body": resp.text})
            buffer.delete(item.row_id)
        except Exception:
            logger.exception("Failed to flush buffered lead")
            break


def _flush_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        _flush_buffer_once()
        stop_event.wait(settings.flush_interval_seconds)


def _build_lead_payload(update: Update) -> dict:
    user = update.effective_user
    username = f"@{user.username}" if user and user.username else None
    return {
        "source": "telegram_bot",
        "telegram_user_id": user.id if user else None,
        "name": user.full_name if user else None,
        "contact": username,
    }


def _build_user_payload(update: Update, *, consent_given: bool | None = None) -> dict:
    user = update.effective_user
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "telegram_id": user.id if user else None,
        "username": user.username if user else None,
        "first_name": user.first_name if user else None,
        "last_name": user.last_name if user else None,
        "name": user.full_name if user else None,
        "last_interaction": now,
    }
    if consent_given is not None:
        payload.update(
            {
                "consent_given": consent_given,
                "consent_date": now if consent_given else None,
                "consent_revoked": False,
            }
        )
    return payload


def _has_pdn_consent(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    try:
        response = core_client.get_users({"telegram_id": user.id, "limit": 1})
        if response.status_code != 200:
            raise RuntimeError(f"core status {response.status_code}")
        rows = response.json()
        return bool(
            rows
            and rows[0].get("consent_given")
            and not rows[0].get("consent_revoked")
        )
    except Exception:
        logger.exception("Failed to read user consent from core")
        return False


async def _send_consent_gate(update: Update) -> None:
    message = update.effective_message
    if message:
        await message.reply_text(
            _consent_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=_consent_keyboard(),
            disable_web_page_preview=True,
        )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = context
    user = update.effective_user
    has_consent = _has_pdn_consent(update)

    if user and not has_consent:
        try:
            core_client.post_user(_build_user_payload(update), idempotency_key=f"bot-start-user-{user.id}")
        except Exception:
            logger.exception("Failed to register bot user before consent")

    try:
        event_payload = {
            "lead_id": None,
            "type": "bot_start",
            "payload": {"telegram_user_id": user.id if user else None, "consent_required": not has_consent},
        }
        core_client.post_event(event_payload, idempotency_key=str(uuid.uuid4()))
    except Exception:
        logger.exception("Failed to send bot_start event")

    if update.message is None:
        return

    if not has_consent:
        await _send_consent_gate(update)
        return

    # Platform map first — sets the context "this bot is part of a bigger
    # thing", inline buttons let the user jump anywhere immediately.
    await update.message.reply_text(
        _platform_map_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=_platform_map_keyboard(),
        disable_web_page_preview=True,
    )

    # Original acknowledgement — same wording, kept so existing scripts and
    # dialog flows don't break.
    await update.message.reply_text(
        "Если хотите, напишите задачу одним сообщением — я передам её менеджеру "
        "и мы вернёмся с предложением."
    )


async def consent_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = context
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if query.data == _CONSENT_DECLINE_CALLBACK:
        await query.edit_message_text(
            "Данные не передаются. Без согласия бот не будет создавать заявку или пересылать сообщение менеджеру."
        )
        return
    if query.data != _CONSENT_ACCEPT_CALLBACK:
        return

    try:
        payload = _build_user_payload(update, consent_given=True)
        response = core_client.post_user(
            payload,
            idempotency_key=f"bot-consent-{payload['telegram_id']}-{_CONSENT_VERSION}",
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(f"core status {response.status_code}: {response.text}")
    except Exception:
        logger.exception("Failed to save bot consent")
        await query.edit_message_text(
            "Не удалось сохранить согласие. Нажмите /start и попробуйте ещё раз."
        )
        return

    await query.edit_message_text(
        "✅ <b>Согласие сохранено</b>\n\nТеперь можно пользоваться ассистентом и отправлять заявку.",
        parse_mode=ParseMode.HTML,
    )
    if query.message:
        await query.message.reply_text(
            _platform_map_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=_platform_map_keyboard(),
            disable_web_page_preview=True,
        )
        await query.message.reply_text(
            "Опишите задачу одним сообщением. Я сохраню контекст и передам его менеджеру."
        )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = context
    if not _has_pdn_consent(update):
        await _send_consent_gate(update)
        return
    payload = _build_lead_payload(update)
    payload["notes"] = update.message.text[:1000] if update.message and update.message.text else None
    idem_key = str(uuid.uuid4())

    try:
        resp = core_client.post_lead(payload, idempotency_key=idem_key)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"core status {resp.status_code}")
    except Exception:
        logger.exception("Core unavailable, buffering lead message")
        buffer.add(payload, idempotency_key=idem_key)

    await update.message.reply_text("Сообщение принято. Спасибо!")


def main() -> None:
    stop_event = threading.Event()
    flush_thread = threading.Thread(target=_flush_loop, args=(stop_event,), daemon=True)
    flush_thread.start()

    if not settings.telegram_bot_token:
        logger.info("TELEGRAM_BOT_TOKEN is empty, only buffer flush loop is active")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()
        return

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(consent_callback_handler, pattern="^consent_pdn_(yes|no)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    try:
        app.run_polling(close_loop=False)
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
