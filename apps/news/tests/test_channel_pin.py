from __future__ import annotations

from news.channel_pin import (
    CHANNEL_DESCRIPTION,
    CHANNEL_TITLE,
    build_channel_pin_keyboard,
    build_channel_pin_text,
)
from news.settings import settings


def test_channel_pin_text_positions_ai_verdict_as_platform() -> None:
    text = build_channel_pin_text()

    assert CHANNEL_TITLE in text
    assert "событиях последних трёх дней" in text
    assert "Основное направление" in text
    assert "автоматизация юридической функции" in text
    assert "юридическая практика" in text
    assert "инженерная практика" in text
    assert "Практика AI Verdict" in text
    assert "Никаких рекламных обещаний" in text


def test_channel_profile_fits_telegram_limits() -> None:
    assert CHANNEL_TITLE == "AI Verdict | ИИ в праве"
    assert len(CHANNEL_TITLE) <= 128
    assert len(CHANNEL_DESCRIPTION) <= 255
    assert "автоматизация юридической функции" in CHANNEL_DESCRIPTION


def test_channel_pin_keyboard_links_to_platform_parts() -> None:
    keyboard = build_channel_pin_keyboard()
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    urls_by_label = {button.text: button.url for button in buttons}

    assert urls_by_label["🌐 Платформа AI Verdict"] == "https://ai-verdict.ru"
    assert urls_by_label["📄 Проверить договор"] == "https://contract.ai-verdict.ru"
    assert urls_by_label["⚙️ Автоматизация юрфункции"] == "https://ai-verdict.ru/solutions"
    assert urls_by_label["⚖️ Юридическая практика"] == "https://ai-verdict.ru/legal-help"
    assert urls_by_label["🛠 Инженерная практика"] == "https://ai-verdict.ru/engineering"
    # Ассистент и reader-бот — разные боты, их нельзя смешивать.
    assistant = urls_by_label["💬 Ассистент"]
    reader = urls_by_label["📰 Reader-бот"]
    assert assistant == f"https://t.me/{settings.news_helper_bot_username}"
    assert reader.startswith("https://t.me/") and reader != assistant
    assert urls_by_label["📱 Mini App"] == "https://ai-verdict.ru/miniapp"
