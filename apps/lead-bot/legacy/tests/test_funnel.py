"""Тесты эвристик воронки и анти-"жидкого" ответа."""

import funnel


def test_infer_stage_uses_pain_hints_without_extracted_fields():
    stage = funnel.infer_stage(
        previous_stage="discover",
        user_message="По-разному, все не систематизировано и теряются заявки",
        lead_data={},
    )
    assert stage == "qualify"


def test_enforce_leadgen_response_adds_structured_question_on_discover():
    result = funnel.enforce_leadgen_response(
        response_text="Понял ваш запрос.",
        stage="discover",
        user_message="по разному и не систематизировано",
        cta_shown=False,
        cta_variant="A",
        lead_data={},
    )

    assert "типичный сигнал разрозненного процесса" in result.lower()
    assert "1)" in result and "2)" in result and "3)" in result


def test_enforce_leadgen_response_adds_missing_qualification_question():
    result = funnel.enforce_leadgen_response(
        response_text="Давайте уточним несколько деталей.",
        stage="qualify",
        user_message="нужна автоматизация заявок",
        cta_shown=False,
        cta_variant="B",
        lead_data={"pain_point": "теряем заявки", "service_category": "Аутсорсинг"},
    )

    assert "сколько юристов" in result.lower()
    assert "1-3" in result


def test_enforce_leadgen_response_keeps_propose_text_without_contact_push():
    result = funnel.enforce_leadgen_response(
        response_text="Предлагаю начать с пилотного сценария.",
        stage="propose",
        user_message="да, интересно",
        cta_shown=False,
        cta_variant="A",
        lead_data={},
    )

    assert result == "Предлагаю начать с пилотного сценария."
    assert funnel.should_show_consultation_button("propose", False) is True
    assert "email или телефон" not in result.lower()


def test_is_cta_shown_accepts_mini_audit_pattern():
    assert funnel.is_cta_shown("Могу провести мини-аудит, оставьте email.", "A")


def test_enforce_leadgen_response_does_not_add_second_question_block():
    result = funnel.enforce_leadgen_response(
        response_text=(
            "Вижу основную проблему в разрозненных каналах.\n"
            "Что сейчас для вас критичнее?\n"
            "1) Скорость\n"
            "2) Контроль сроков\n"
            "3) Снижение потерь"
        ),
        stage="discover",
        user_message="теряем заявки",
        cta_shown=False,
        cta_variant="A",
        lead_data={},
    )
    assert result.count("1)") == 1


def test_should_fast_track_handoff_when_contact_and_consultation_requested():
    assert funnel.should_fast_track_handoff(
        "Готов на консультацию, мой телефон +7 909 233-09-09",
        {},
    ) is True
