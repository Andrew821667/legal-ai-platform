"""Помощник, ведущий первичный разговор с клиентом.

Главное здесь — граница второго уровня. Пока вопросы были заданы в коде, выйти
за неё было физически нельзя. Теперь говорит модель, и граница держится
промптом и проверкой готовой реплики. Эти проверки закрепляют вторую половину:
что именно не должно дойти до клиента.
"""

from __future__ import annotations

import json

import pytest
from core_api import intake_assistant
from core_api.intake_assistant import (
    MAX_QUESTIONS,
    MIN_QUESTIONS,
    build_system_prompt,
    check_reply,
    next_turn,
)
from core_api.model_client import ChatResult


def _prompt() -> str:
    return build_system_prompt(
        assistant_name="Никита",
        area_label="трудовые отношения",
        base_questions=["Вы работник или работодатель?"],
        asked_count=1,
    )


def test_assistant_introduces_itself_as_ai() -> None:
    """Клиент должен понимать, кому рассказывает обстоятельства своей жизни.

    Скрыть это — значит выиграть немного доверия сейчас и потерять всё, когда
    человек узнает.
    """
    prompt = _prompt()
    assert "ИИ-помощник" in prompt
    assert "человек ли ты" in prompt


def test_prompt_forbids_assessment_advice_and_norms() -> None:
    prompt = _prompt().lower()
    for phrase in (
        "не оценивай ситуацию",
        "не предсказывай исход",
        "не советуй",
        "не ссылайся на статьи",
        "правовую оценку даёт юрист",
    ):
        assert phrase in prompt, phrase


def test_prompt_states_the_question_budget() -> None:
    prompt = build_system_prompt(
        assistant_name="Никита", area_label="спор", base_questions=["Вопрос"], asked_count=5
    )
    assert str(MAX_QUESTIONS) in prompt
    assert "осталось не больше 2" in prompt


def test_question_budget_is_sane() -> None:
    assert MIN_QUESTIONS < MAX_QUESTIONS
    assert MAX_QUESTIONS <= 7


@pytest.mark.parametrize(
    "reply",
    [
        "Я рекомендую подать иск в течение месяца.",
        "Советую обратиться в трудовую инспекцию.",
        "Вам следует подать заявление как можно скорее.",
        "У вас хорошие шансы взыскать эту сумму.",
        "Суд встанет на вашу сторону, это очевидно.",
        "Вы правы, работодатель нарушил порядок.",
        "Это незаконно со стороны банка.",
        "Здесь налицо нарушение ваших прав.",
        "Согласно статье 392 срок составляет месяц.",
        "По ст. 1152 наследство принимается в течение полугода.",
    ],
)
def test_reply_crossing_the_line_is_blocked(reply: str) -> None:
    assert check_reply(reply) is not None, reply


@pytest.mark.parametrize(
    "reply",
    [
        "Понял вас. Подскажите, какого числа вам вручили приказ?",
        "Спасибо, это важно. А договор у вас на руках?",
        "Записал. Юрист посмотрит материалы и свяжется с вами.",
        "Уточню ещё одно: заявление вы подавали письменно или устно?",
        "Я ИИ-помощник юриста, собираю предварительные сведения.",
    ],
)
def test_ordinary_reply_passes(reply: str) -> None:
    assert check_reply(reply) is None, reply


def _stub(monkeypatch: pytest.MonkeyPatch, result: ChatResult) -> None:
    monkeypatch.setattr(intake_assistant, "chat", lambda *args, **kwargs: result)


def _turn(**kwargs):
    defaults = dict(
        intake={"description": "Уволили без объяснения причин."},
        history=[{"role": "client", "text": "Здравствуйте"}],
        base_questions=["Вы работник или работодатель?"],
        area_label="трудовые отношения",
        asked_count=1,
        api_key="test-key",
    )
    defaults.update(kwargs)
    return next_turn(**defaults)


def test_reply_reaches_the_client_with_its_cost(monkeypatch) -> None:
    _stub(
        monkeypatch,
        ChatResult(
            text=json.dumps({"reply": "Понял вас. Какого числа это произошло?", "done": False}),
            model="gpt-5.6-sol",
            prompt_tokens=500,
            completion_tokens=40,
            cost_usd=0.0028,
        ),
    )
    turn = _turn()

    assert turn.ok
    assert turn.text == "Понял вас. Какого числа это произошло?"
    assert turn.finished is False
    assert turn.cost_usd == 0.0028


def test_blocked_reply_never_reaches_the_client(monkeypatch) -> None:
    """Реплика за границей не отправляется и не переспрашивается.

    Модель уже показала, куда её ведёт; вызывающая сторона вернётся к
    заданным в коде вопросам — разговор станет суше, но останется в рамках.
    """
    _stub(
        monkeypatch,
        ChatResult(
            text=json.dumps({"reply": "У вас хорошие шансы выиграть дело.", "done": False}),
            model="gpt-5.6-sol",
            cost_usd=0.001,
        ),
    )
    turn = _turn()

    assert turn.text == ""
    assert turn.error == "blocked"
    assert turn.blocked_reason == "прогноз"
    # Стоимость всё равно учитывается: запрос был оплачен.
    assert turn.cost_usd == 0.001


def test_non_json_answer_is_not_guessed(monkeypatch) -> None:
    """Разбирать свободный текст догадками — значит отправить клиенту неизвестно что."""
    _stub(monkeypatch, ChatResult(text="Конечно! Расскажите подробнее.", model="gpt-5.6-sol"))
    turn = _turn()

    assert turn.text == ""
    assert turn.error == "bad_json"


def test_model_failure_is_reported_not_raised(monkeypatch) -> None:
    _stub(monkeypatch, ChatResult(text="", model="gpt-5.6-sol", error="TimeoutError"))
    turn = _turn()

    assert turn.ok is False
    assert turn.error == "TimeoutError"


def test_question_budget_ends_the_conversation(monkeypatch) -> None:
    """Дойдя до предела, помощник завершает расспросы, даже если модель хочет ещё."""
    _stub(
        monkeypatch,
        ChatResult(
            text=json.dumps({"reply": "И последнее: где вы работали?", "done": False}),
            model="gpt-5.6-sol",
        ),
    )
    turn = _turn(asked_count=MAX_QUESTIONS)

    assert turn.finished is True


def test_missing_key_does_not_raise() -> None:
    turn = _turn(api_key="")
    assert turn.ok is False
    assert turn.error == "api_key_missing"
