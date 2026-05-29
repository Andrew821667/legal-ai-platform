from __future__ import annotations

import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from news.settings import settings


def _site_url() -> str:
    return (
        os.getenv("PUBLIC_SITE_URL")
        or os.getenv("NEXT_PUBLIC_SITE_URL")
        or "https://ai-verdict.ru"
    ).rstrip("/")


def _contract_url() -> str:
    return (
        os.getenv("CONTRACT_AI_SYSTEM_URL")
        or os.getenv("NEXT_PUBLIC_CONTRACT_AI_URL")
        or "https://contract.ai-verdict.ru"
    ).rstrip("/")


def _bot_url(username: str) -> str:
    return f"https://t.me/{username.strip().lstrip('@')}"


def build_channel_pin_text() -> str:
    return (
        "<b>Привет, я Андрей Попов.</b>\n\n"
        "Я юрист и разработчик AI-решений для автоматизации юридической работы. "
        "В этом канале разбираю, как искусственный интеллект уже меняет работу "
        "юристов, юрдепов и бизнеса: договоры, судебную работу, комплаенс, "
        "legal ops, аналитику и рабочие AI-инструменты без лишнего шума.\n\n"
        "Канал — это часть платформы <b>AI Verdict</b>. Она помогает не только "
        "читать про Legal AI, но и переходить к практике:\n"
        "• 🌐 <b>сайт</b> — продукты, услуги, методология и заявка на консультацию\n"
        "• 📄 <b>Contract AI</b> — проверка договоров, риски и рекомендации по правкам\n"
        "• 💬 <b>ассистент</b> — вопрос, демо, заявка или маршрут внедрения\n"
        "• 📰 <b>reader-бот</b> — персональная лента и разборы материалов канала\n"
        "• 📱 <b>Mini App</b> — контент, инструменты, профиль и заявка внутри Telegram\n\n"
        "Можно начинать с любого элемента: прочитать пост, задать вопрос ассистенту, "
        "проверить договор или открыть Mini App. Контекст и заявки внутри платформы "
        "не теряются."
    )


def build_channel_pin_keyboard() -> InlineKeyboardMarkup:
    site_url = _site_url()
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌐 Платформа AI Verdict", url=site_url)],
            [InlineKeyboardButton("📄 Проверить договор", url=_contract_url())],
            [
                InlineKeyboardButton("💬 Задать вопрос", url=_bot_url(settings.lead_bot_username)),
                InlineKeyboardButton("📰 Reader-бот", url=_bot_url(settings.news_helper_bot_username)),
            ],
            [InlineKeyboardButton("📱 Mini App", url=f"{site_url}/miniapp")],
        ]
    )
