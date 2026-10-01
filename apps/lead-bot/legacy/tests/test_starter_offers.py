"""Цены первых шагов в боте и на сайте — одни и те же.

Бот называл проекты от 100–500 тыс. ₽, сайт — консультацию за 4 900 ₽:
клиент видел две разные компании. Источник — apps/web/lib/starter-offers.ts.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import content
import funnel
from handlers import constants, markup

_SITE_OFFERS = Path(__file__).resolve().parents[3] / "web" / "lib" / "starter-offers.ts"


def _site_offers() -> list[tuple[str, str]]:
    text = _SITE_OFFERS.read_text(encoding="utf-8")
    return re.findall(r'title: "([^"]+)",\s*price: "([^"]+)"', text)


@pytest.mark.skipif(not _SITE_OFFERS.exists(), reason="нет исходников сайта рядом (образ бота)")
def test_bot_first_steps_match_site() -> None:
    bot = [(title, price) for _, title, price, _ in content.STARTER_OFFERS]
    assert bot == _site_offers()


def test_consultation_price_is_the_site_price() -> None:
    assert content.CONSULTATION_PRICE_TEXT == content.STARTER_OFFERS[0][2]


def _buttons(rows) -> list[tuple[str, str | None, str | None]]:
    return [(b.text, getattr(b, "url", None), getattr(b, "callback_data", None)) for row in rows for b in row]


def test_next_step_buttons_follow_the_intent() -> None:
    config = constants.get_config()
    legal = _buttons(constants.build_consultation_cta_menu("new_legal_task"))
    assert [url for _, url, _ in legal if url] == [config.CONSULTATION_BOOKING_URL]
    dev = _buttons(constants.build_consultation_cta_menu("dev_task"))
    assert [url for _, url, _ in dev if url] == [config.AUTOMATION_DIAGNOSTIC_URL]
    unclear = _buttons(constants.build_consultation_cta_menu("unclear"))
    assert [url for _, url, _ in unclear if url] == [config.CONSULTATION_BOOKING_URL, config.AUTOMATION_DIAGNOSTIC_URL]
    # Цена — на кнопке; «обсудить» ведёт в выбор контакта, а не к телефону сразу.
    assert "4 900 ₽" in legal[0][0] and "7 900 ₽" in dev[0][0]
    assert legal[-1][2] == "menu_leave_contact"


def test_consultation_button_offers_booking_or_contact() -> None:
    buttons = _buttons(markup.consultation_choice_markup().inline_keyboard)
    assert buttons[0][1] == constants.get_config().CONSULTATION_BOOKING_URL
    assert [data for _, _, data in buttons[1:]] == ["menu_contact_send_phone", "menu_contact_telegram_only"]


def test_lead_magnets_promise_nothing_free_from_the_lawyer() -> None:
    texts = [content.LEAD_MAGNET_OFFER_TEXT, *content.LEAD_MAGNET_SELECTION_MESSAGES.values()]
    joined = "\n".join(texts).lower()
    assert "демонстрационный разбор" not in joined
    assert "4 900 ₽" in content.LEAD_MAGNET_SELECTION_MESSAGES["consultation"]
    labels = [b.text for row in constants.LEAD_MAGNET_MENU for b in row]
    assert "📞 Консультация юриста — 4 900 ₽" in labels


def test_is_cta_shown_recognizes_paid_diagnostic() -> None:
    assert funnel.is_cta_shown("Следующий шаг — диагностика за 7 900 ₽.", "A")


def test_materials_are_offered_and_delivered_right_in_the_chat() -> None:
    # Писем клиентам нет: чек-лист и образец отчёта бот отдаёт прямо в чате.
    menu = [b.callback_data for row in constants.LEAD_MAGNET_MENU for b in row]
    assert menu == ["magnet_consultation", "magnet_checklist", "magnet_demo", "magnet_sample_report"]
    for magnet in content.INSTANT_MAGNETS:
        text = content.LEAD_MAGNET_SELECTION_MESSAGES[magnet]
        assert "email" not in text.lower() and "почт" not in text.lower()
        assert len(text) < 4096  # одно сообщение Telegram
    assert "15. " in content.CHECKLIST_MESSAGE
    assert "Чек-лист" in content.LEAD_MAGNET_OFFER_TEXT and "Образец отчёта" in content.LEAD_MAGNET_OFFER_TEXT
    # Договор проверяют в Contract AI — кнопка ведёт туда, бот файлы не принимает.
    contract_ai, consultation = (row[0] for row in constants.MAGNET_FOLLOWUP_MENU)
    assert contract_ai.url.startswith("https://") and contract_ai.url.endswith("/demo")
    assert consultation.callback_data == "magnet_consultation"
    assert "пришлите" not in content.DEMO_MESSAGE.lower() and "сюда" not in content.DEMO_MESSAGE


def test_magnet_reply_gives_material_and_next_step() -> None:
    from handlers.helpers import magnet_reply

    text, markup = magnet_reply("checklist")
    assert text == content.CHECKLIST_MESSAGE
    assert [b.callback_data for row in markup.inline_keyboard for b in row] == [None, "magnet_consultation"]
    text, markup = magnet_reply("demo")
    assert text == content.DEMO_MESSAGE and markup.inline_keyboard[0][0].url
    text, markup = magnet_reply("sample_report")
    assert text == content.SAMPLE_REPORT_MESSAGE and markup is not None
    text, markup = magnet_reply("consultation")
    assert "4 900" in text and markup is None


@pytest.mark.asyncio
async def test_contract_file_is_sent_to_contract_ai_not_taken_by_the_bot() -> None:
    from types import SimpleNamespace

    from handlers import user_non_text

    replies = []

    async def _reply(message, text, **kwargs):
        replies.append((text, kwargs.get("reply_markup")))

    original = user_non_text.utils.safe_reply_text
    user_non_text.utils.safe_reply_text = _reply
    try:
        message = SimpleNamespace(document=SimpleNamespace(file_name="договор.pdf"), photo=None, contact=None, caption=None)
        update = SimpleNamespace(effective_message=message, update_id=1, effective_user=None)
        handled = await user_non_text.handle_non_text_input(update, None, {"id": 1}, None, True)
    finally:
        user_non_text.utils.safe_reply_text = original
    assert handled is True
    text, markup = replies[0]
    assert "Contract AI" in text
    assert markup.inline_keyboard[0][0].url
