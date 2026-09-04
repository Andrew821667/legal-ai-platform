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
    """Помощник может назваться по имени, но не выдавать себя за сотрудника.

    Клиент, уверенный что пишет юристу, раскроет больше, чем следует, — а
    адвокатской тайны в переписке с ИИ нет.

    Прежняя редакция этой проверки запрещала само «меня зовут»: тогда имени не
    было вовсе, и безымянность была единственным способом не ввести человека в
    заблуждение. Теперь имя есть, и ту же задачу решает прямое указание, что
    собеседник — ИИ. Проверяем суть, а не формулировку.
    """
    text = build_outreach_message(BASE)
    lowered = text.lower()

    assert "ии-помощник" in lowered
    for claim in ("я юрист", "я адвокат", "ваш юрист", "сотрудник практики"):
        assert claim not in lowered


def test_message_uses_client_name_when_known() -> None:
    with_name = build_outreach_message({**BASE, "name": "Андрей"})
    without_name = build_outreach_message(BASE)

    assert "Андрей" in with_name
    assert "Андрей" not in without_name
    assert without_name.startswith("Здравствуйте")


def test_message_mentions_the_legal_area() -> None:
    """Упоминание темы показывает, что заявку прочитали, а не отписались.

    Здесь стоит реальное значение из перечисления LegalArea. В прежней
    редакции теста был выдуманный ключ «labor», совпадавший с такой же
    выдумкой в самом модуле, — тест проходил и не проверял ничего.
    Совпадение всего набора ключей с перечислением закреплено отдельно
    в tests/test_intake_dialog.py.
    """
    text = build_outreach_message({**BASE, "legal_area": "employment"})

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


def test_assistant_introduces_itself_by_name() -> None:
    """У клиента должен быть собеседник, а не служба.

    Обращение приходит в тяжёлый момент, и разница между «ассистент команды» и
    «Никита, помощник юриста» решает, расскажет ли человек обстоятельства.
    """
    text = build_outreach_message(BASE)
    assert "Никита" in text
    assert "помощник юриста" in text


def test_assistant_says_it_is_ai() -> None:
    """Клиент раскрывает обстоятельства своей жизни — он должен знать кому.

    Скрыть это значит выиграть немного доверия сейчас и потерять всё, когда
    человек узнает. Заодно снимается риск, что он сочтёт разговор защищённым
    адвокатской тайной.
    """
    assert "ИИ-помощник" in build_outreach_message(BASE)


def test_message_does_not_promise_legal_help_itself() -> None:
    """Помощник собирает сведения, а не консультирует."""
    text = build_outreach_message(BASE).lower()
    for phrase in ("проконсультирую", "дам оценку", "решу ваш вопрос", "помогу выиграть"):
        assert phrase not in text
