"""Inline-keyboard "platform map" greeting for /start.

Mirrors the layout produced by apps/web/components/PlatformMap.tsx so a
user landing in the Telegram bot sees the same platform parts
they'd see on the site, instead of treating the bot as a standalone tool.

Keep these parts here in sync with apps/web/lib/platformParts.ts.
"""
from __future__ import annotations

import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import get_config

_config = get_config()


_INTRO = (
    "👋 Я ассистент <b>AI Verdict</b>. Опишите задачу своими словами, проверьте договор "
    "или выберите нужный раздел. Правовой вопрос передам юристу, задачу по разработке — инженеру.\n\n"
    "Точки входа:"
)

_PART_LINES = (
    "🌐 <b>Сайт</b> — продукты, услуги, методология и заявка на консультацию",
    "📄 <b>Contract AI</b> — проверка договоров, риски и рекомендации по правкам",
    "💬 <b>Ассистент</b> — вопросы, демо, заявки и маршрут внедрения",
    "📰 <b>Новостной контур</b> — канал и reader-бот с разборами AI в legal",
    "📱 <b>Mini App</b> — персональный контур: контент, инструменты, профиль и заявка",
    "⚖️ <b>Юридическая помощь</b> — быстро передать правовую задачу юристу",
)


def _site_url() -> str:
    return (
        os.getenv("LEAD_BOT_PUBLIC_SITE_URL")
        or os.getenv("PUBLIC_SITE_URL")
        or os.getenv("NEXT_PUBLIC_SITE_URL")
        or "https://ai-verdict.ru"
    ).rstrip("/")


def _channel_url() -> str:
    if _config.TELEGRAM_CHANNEL_URL:
        return _config.TELEGRAM_CHANNEL_URL
    username = (_config.TELEGRAM_CHANNEL_USERNAME or "ai_verdict").lstrip("@")
    return f"https://t.me/{username}"


def _reader_bot_url() -> str:
    username = (
        os.getenv("LEAD_PUBLIC_READER_BOT_USERNAME")
        or os.getenv("NEXT_PUBLIC_READER_BOT_USERNAME")
        or "legal_ai_news_reader_bot"
    ).lstrip("@")
    return f"https://t.me/{username}"


def _contract_url() -> str:
    return _config.CONTRACT_AI_SYSTEM_URL or "https://contract.ai-verdict.ru"


def build_text() -> str:
    """HTML-formatted greeting body."""
    return _INTRO + "\n\n" + "\n".join(_PART_LINES)


def build_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard giving one-tap entry into each part of the platform."""
    site_url = _site_url()
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("🌐 Открыть сайт", url=site_url)],
        [InlineKeyboardButton("⚖️ Юридическая помощь", callback_data="legal_help_start")],
        [InlineKeyboardButton("📄 Contract AI", url=_contract_url())],
        [
            InlineKeyboardButton("📰 Канал", url=_channel_url()),
            InlineKeyboardButton("📰 Reader-бот", url=_reader_bot_url()),
        ],
        [InlineKeyboardButton("📱 Mini App на сайте", url=f"{site_url}/miniapp")],
    ]
    return InlineKeyboardMarkup(rows)
