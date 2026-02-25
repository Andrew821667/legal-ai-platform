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


def test_enforce_leadgen_response_adds_cta_on_propose():
    result = funnel.enforce_leadgen_response(
        response_text="Предлагаю начать с пилотного сценария.",
        stage="propose",
        user_message="да, интересно",
        cta_shown=False,
        cta_variant="A",
        lead_data={},
    )

    assert "консультация 30 минут" in result.lower()
    assert "email или телефон" in result.lower()


def test_is_cta_shown_accepts_mini_audit_pattern():
    assert funnel.is_cta_shown("Могу провести мини-аудит, оставьте email.", "A")
