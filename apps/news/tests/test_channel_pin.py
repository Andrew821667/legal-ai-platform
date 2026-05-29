from __future__ import annotations

from news.channel_pin import build_channel_pin_keyboard, build_channel_pin_text


def test_channel_pin_text_positions_ai_verdict_as_platform() -> None:
    text = build_channel_pin_text()

    assert "Привет, я Андрей Попов" in text
    assert "В этом канале разбираю" in text
    assert "Канал — это часть платформы" in text
    assert "Contract AI" in text
    assert "Mini App" in text
    assert "Контекст и заявки внутри платформы" in text


def test_channel_pin_keyboard_links_to_platform_parts() -> None:
    keyboard = build_channel_pin_keyboard()
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    urls_by_label = {button.text: button.url for button in buttons}

    assert urls_by_label["🌐 Платформа AI Verdict"] == "https://ai-verdict.ru"
    assert urls_by_label["📄 Проверить договор"] == "https://contract.ai-verdict.ru"
    assert urls_by_label["💬 Задать вопрос"].startswith("https://t.me/")
    assert urls_by_label["📰 Reader-бот"].startswith("https://t.me/")
    assert urls_by_label["📱 Mini App"] == "https://ai-verdict.ru/miniapp"
