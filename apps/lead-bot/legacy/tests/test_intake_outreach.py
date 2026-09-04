"""Первое обращение к клиенту после юридической заявки.

Человек оставил заявку и ждёт. Сообщение должно показать, что обращение попало
к людям, не выдавая при этом бота за сотрудника: если клиент решит, что пишет
юристу, он может раскрыть детали, полагаясь на адвокатскую тайну.
"""

from __future__ import annotations

import sys
from pathlib import Path

LEGACY = Path(__file__).resolve().parents[1]
if str(LEGACY) not in sys.path:
    sys.path.insert(0, str(LEGACY))

from intake_outreach import build_no_contact_note, build_outreach_message  # noqa: E402

BASE = {"legal_area": "contracts", "client_type": "business", "urgency": "normal"}


def test_message_does_not_impersonate_a_human() -> None:
    """Бот не должен представляться сотрудником.

    Клиент, уверенный что пишет юристу, раскроет больше, чем следует, —
    а адвокатской тайны в переписке с ботом нет.
    """
    text = build_outreach_message(BASE)

    assert "ассистент" in text.lower()
    assert "меня зовут" not in text.lower()


def test_message_uses_client_name_when_known() -> None:
    with_name = build_outreach_message({**BASE, "name": "Андрей"})
    without_name = build_outreach_message(BASE)

    assert "Андрей" in with_name
    assert "Андрей" not in without_name
    assert without_name.startswith("Здравствуйте")


def test_message_mentions_the_legal_area() -> None:
    """Упоминание темы показывает, что заявку прочитали, а не отписались."""
    text = build_outreach_message({**BASE, "legal_area": "labor"})

    assert "трудов" in text


def test_unknown_area_does_not_break_the_message() -> None:
    text = build_outreach_message({**BASE, "legal_area": "нет-такой-области"})

    assert "вашей ситуации" in text


def test_urgent_case_is_acknowledged() -> None:
    urgent = build_outreach_message({**BASE, "urgency": "urgent"})
    normal = build_outreach_message({**BASE, "urgency": "normal"})

    assert "срочный" in urgent
    assert urgent != normal


def test_message_offers_a_way_to_reach_a_human() -> None:
    """Человек не должен чувствовать себя запертым в диалоге с ботом."""
    text = build_outreach_message(BASE)

    assert "юрист" in text.lower()


def test_message_promises_no_outcome() -> None:
    """Оценка перспектив — работа юриста, а не первого сообщения."""
    text = build_outreach_message(BASE).lower()

    for forbidden in ("выиграем", "гарантируем", "решим ваш вопрос", "успех"):
        assert forbidden not in text


def test_no_contact_note_explains_the_reason() -> None:
    """Юрист должен понять, что это ограничение Telegram, а не сбой."""
    note = build_no_contact_note({"intake_id": "abc-123", "name": "Андрей"})

    assert "abc-123" in note
    assert "Telegram" in note
    assert "вручную" in note
