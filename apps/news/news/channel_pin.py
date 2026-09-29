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
    # Канал многопрофильный, как и платформа: право РФ, автоматизация
    # юридической работы и ИИ — не только лента новостей Legal AI.
    return (
        "<b>Привет, я Андрей Попов.</b>\n\n"
        "Я юрист и разработчик систем автоматизации юридической работы. "
        "В этом канале разбираю три темы: важные изменения права РФ для бизнеса "
        "и граждан, автоматизацию юридической работы и то, как искусственный "
        "интеллект меняет работу юристов, юрдепов и бизнеса — договоры, споры, "
        "комплаенс, персональные данные.\n\n"
        "Канал — это часть платформы <b>AI Verdict</b>. От чтения можно сразу "
        "перейти к делу:\n"
        "• ⚖️ <b>юридическая практика</b> — консультация юриста онлайн (4 900 ₽), "
        "проверка договора, претензия\n"
        "• 🛠 <b>инженерная практика</b> — боты, сайты, AI-сервисы и интеграции\n"
        "• 📄 <b>Contract AI</b> — проверка договоров, риски и рекомендации по правкам\n"
        "• 💬 <b>ассистент</b> — вопрос, заявка или маршрут внедрения\n"
        "• 📰 <b>reader-бот</b> — персональная лента и разборы материалов канала\n"
        "• 📱 <b>Mini App</b> — контент, инструменты, профиль и заявка внутри Telegram\n\n"
        "Можно начинать с любого элемента: прочитать пост, задать вопрос ассистенту, "
        "записаться к юристу или проверить договор. Контекст и заявки внутри платформы "
        "не теряются."
    )


def build_channel_pin_keyboard() -> InlineKeyboardMarkup:
    site_url = _site_url()
    # Ассистент и reader-бот — разные боты. Раньше «📰 Reader-бот» вёл на
    # ассистента (news_helper_bot_username), а «💬 Задать вопрос» — на
    # @AI_Verdict_Popov_Andrew, которого больше нигде в платформе нет.
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌐 Платформа AI Verdict", url=site_url)],
            [InlineKeyboardButton("📅 Консультация юриста — 4 900 ₽", url=f"{site_url}/consultation")],
            [InlineKeyboardButton("📄 Проверить договор", url=_contract_url())],
            [
                InlineKeyboardButton("💬 Ассистент", url=_bot_url(settings.news_helper_bot_username)),
                InlineKeyboardButton("📰 Reader-бот", url=settings.reader_bot_url),
            ],
            [InlineKeyboardButton("📱 Mini App", url=f"{site_url}/miniapp")],
        ]
    )
