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
