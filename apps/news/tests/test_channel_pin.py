from __future__ import annotations

from news.channel_pin import build_channel_pin_keyboard, build_channel_pin_text
from news.settings import settings


def test_channel_pin_text_positions_ai_verdict_as_platform() -> None:
    text = build_channel_pin_text()

    assert "Привет, я Андрей Попов" in text
    assert "В этом канале разбираю" in text
    assert "Канал — это часть платформы" in text
    assert "Contract AI" in text
    assert "Mini App" in text
    assert "Контекст и заявки внутри платформы" in text
    # Многопрофильность: право РФ, автоматизация и ИИ.
    assert "права РФ" in text and "автоматизацию юридической работы" in text


def test_channel_pin_keyboard_links_to_platform_parts() -> None:
    keyboard = build_channel_pin_keyboard()
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    urls_by_label = {button.text: button.url for button in buttons}

    assert urls_by_label["🌐 Платформа AI Verdict"] == "https://ai-verdict.ru"
    assert urls_by_label["📄 Проверить договор"] == "https://contract.ai-verdict.ru"
    assert urls_by_label["📅 Консультация юриста — 4 900 ₽"] == "https://ai-verdict.ru/consultation"
    # Ассистент и reader-бот — разные боты, их нельзя смешивать.
    assistant = urls_by_label["💬 Ассистент"]
    reader = urls_by_label["📰 Reader-бот"]
    assert assistant == f"https://t.me/{settings.news_helper_bot_username}"
    assert reader.startswith("https://t.me/") and reader != assistant
    assert urls_by_label["📱 Mini App"] == "https://ai-verdict.ru/miniapp"
