from __future__ import annotations

import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from news.settings import settings

CHANNEL_TITLE = "AI Verdict | ИИ в праве"
CHANNEL_DESCRIPTION = (
    "Проверяем новости об ИИ и объясняем, что они меняют в праве, юридической "
    "работе и бизнесе. Основная практика AI Verdict: автоматизация юридической "
    "функции. Отдельно работают юридическое и инженерное направления. ai-verdict.ru"
)


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
        "<b>AI Verdict | ИИ в праве</b>\n\n"
        "Меня зовут Андрей Попов. Я юрист с многолетней практикой и разработчик "
        "систем автоматизации. Здесь мы не пересказываем всё, что случилось в мире "
        "нейросетей. Берём проверенный факт и разбираем, что он меняет в работе "
        "юриста, компании или конкретного процесса.\n\n"
        "Новостные материалы строятся на событиях последних трёх дней. В каждом "
        "разборе должны быть первичный источник, практический смысл и честно "
        "обозначенные ограничения.\n\n"
        "<b>О чём пишем</b>\n"
        "• автоматизация юридических бизнес-процессов и Legal Ops;\n"
        "• ИИ в договорной, судебной работе и корпоративных базах знаний;\n"
        "• регулирование ИИ, персональные данные и ответственность;\n"
        "• практика внедрения: где технология помогает, а где создаёт новый риск.\n\n"
        "AI Verdict работает на стыке права и разработки. Основное направление: "
        "<b>автоматизация юридической функции</b>. Отдельные задачи ведут два "
        "профильных подразделения: <b>юридическая практика</b> помогает по правовым "
        "вопросам, а <b>инженерная практика</b> создаёт ботов, сайты, приложения, "
        "AI/RAG-системы и интеграции.\n\n"
        "Раз в неделю выходит рубрика <b>«Практика AI Verdict»</b>. В ней показываем "
        "реальные типы задач, границы работы и понятный первый шаг. Никаких рекламных "
        "обещаний и выдуманных кейсов.\n\n"
        "Ниже собраны прямые маршруты к платформе, инструментам и нужному подразделению."
    )


def build_channel_pin_keyboard() -> InlineKeyboardMarkup:
    site_url = _site_url()
    # Ассистент и reader-бот — разные боты. Раньше «📰 Reader-бот» вёл на
    # ассистента (news_helper_bot_username), а «💬 Задать вопрос» — на
    # @AI_Verdict_Popov_Andrew, которого больше нигде в платформе нет.
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌐 Платформа AI Verdict", url=site_url)],
            [InlineKeyboardButton("⚙️ Автоматизация юрфункции", url=f"{site_url}/solutions")],
            [
                InlineKeyboardButton("⚖️ Юридическая практика", url=f"{site_url}/legal-help"),
                InlineKeyboardButton("🛠 Инженерная практика", url=f"{site_url}/engineering"),
            ],
            [InlineKeyboardButton("📄 Проверить договор", url=_contract_url())],
            [
                InlineKeyboardButton("💬 Ассистент", url=_bot_url(settings.news_helper_bot_username)),
                InlineKeyboardButton("📰 Reader-бот", url=settings.reader_bot_url),
            ],
            [InlineKeyboardButton("📱 Mini App", url=f"{site_url}/miniapp")],
        ]
    )
