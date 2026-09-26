"""Черновик условий договора по обращению.

Закрепляется главное: деньги модель не предлагает — стоимость и оплата
только из заготовки, на которую она сослалась; граница без правовых оценок и
обещаний держится промптом, а обещание в готовом тексте видно юристу; сбой
модели — понятный отказ, а не пустая форма. Модель везде подменена: платный
ключ тестам не нужен.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from core_api import terms_draft
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.model_client import ChatResult
from core_api.models import (
    AgreementTemplate,
    AuditLog,
    Lead,
    LeadSource,
    LegalIntake,
    LegalIntakeStatus,
    Practice,
    Scope,
)
from core_api.terms_draft import SYSTEM_PROMPT, build_messages, parse_reply
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_client_archive import _cleanup, _key


def _template(**kwargs) -> AgreementTemplate:
    values = {
        "name": "Проверка договора",
        "practice": Practice.legal,
        "subject": "Правовой анализ договора",
        "scope_text": "1. Изучить договор.\n2. Подготовить замечания.",
        "exclusions_text": "Переговоры с контрагентом",
        "schedule_text": "Три рабочих дня",
        "price_text": "15 000 ₽",
        "amount_minor": 1_500_000,
        "payment_terms": "100% до начала работы",
    }
    values.update(kwargs)
    return AgreementTemplate(**values)


def _reply(**kwargs) -> str:
    data = {
        "subject": "Правовой анализ договора аренды офиса",
        "scope_text": "1. Изучить договор аренды.\n2. Подготовить письменные замечания.",
        "exclusions_text": "Переговоры с арендодателем",
        "schedule_text": "Пять рабочих дней",
        "template": 1,
        "notes": ["Уточнить, подписан ли договор"],
    }
    data.update(kwargs)
    return json.dumps(data, ensure_ascii=False)


def test_prompt_keeps_the_line_and_leaves_money_to_the_lawyer() -> None:
    prompt = SYSTEM_PROMPT.lower()
    for phrase in (
        "не давай правовых оценок",
        "не предсказывай исход",
        "не обещай результат",
        "не называй стоимость и порядок оплаты",
        "не достраивай ситуацию догадками",
    ):
        assert phrase in prompt, phrase


def test_model_never_sees_template_prices() -> None:
    """Увиденную цену легко «подправить» — поэтому модели её не показываем."""
    intake = LegalIntake(description="Нужно проверить договор аренды офиса.", practice=Practice.legal)
    content = build_messages(intake, [_template()])[1]["content"]
    assert "Правовой анализ договора" in content
    assert "15 000" not in content and "100% до начала" not in content


def test_money_comes_only_from_the_template_the_model_chose() -> None:
    templates = [_template(), _template(name="Консультация", price_text="5 000 ₽", amount_minor=500_000)]
    # Модель вписала цену сама — её не берём: только из заготовки.
    draft = parse_reply(_reply(template=2, price_text="1 000 000 ₽", payment_terms="в рассрочку"), templates)
    assert draft.ok
    assert draft.fields["price_text"] == "5 000 ₽"
    assert draft.amount_minor == 500_000
    assert draft.fields["payment_terms"] == "100% до начала работы"
    assert draft.template is templates[1]
    assert draft.fields["subject"] == "Правовой анализ договора аренды офиса"


@pytest.mark.parametrize("number", [None, 0, 3, True, "1", 1.0])
def test_no_valid_template_means_no_money(number) -> None:
    draft = parse_reply(_reply(template=number), [_template(), _template()])
    assert draft.ok
    assert draft.template is None
    assert draft.amount_minor is None
    assert draft.fields["price_text"] == "" and draft.fields["payment_terms"] == ""


def test_promised_outcome_is_flagged_for_the_lawyer() -> None:
    draft = parse_reply(
        _reply(scope_text="1. Подготовить иск.\n2. Гарантируем положительный результат в суде."),
        [],
    )
    assert draft.notes[0].startswith("В тексте есть обещание результата")
    # Обычное условие о конфиденциальности — не обещание исхода.
    calm = parse_reply(_reply(exclusions_text="Исполнитель гарантирует конфиденциальность сведений."), [])
    assert not any("обещание" in note for note in calm.notes)


def test_bad_or_empty_reply_is_not_a_draft() -> None:
    assert parse_reply("Вот условия: предмет — …", []).error == "bad_json"
    assert parse_reply("[1, 2]", []).error == "bad_json"
    assert parse_reply(_reply(subject="", scope_text=""), []).error == "empty_reply"


def test_fields_are_cut_to_what_the_agreement_accepts() -> None:
    draft = parse_reply(_reply(subject="П" * 5000, notes=["x"] * 10 + [5]), [])
    assert len(draft.fields["subject"]) == 4000
    assert len(draft.notes) == terms_draft.MAX_NOTES


# ---- Эндпоинт -------------------------------------------------------------


@pytest.fixture()
def seeded(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INTAKE_ANALYSIS_API_KEY", "test-not-a-real-key")
    get_settings.cache_clear()
    name = f"pytest.terms.{uuid4().hex}"
    db = SessionLocal()
    try:
        lead = Lead(name="Черновик", contact=f"terms-{uuid4().hex[:6]}@example.com", source=LeadSource.website_form)
        db.add(lead)
        db.flush()
        intake = LegalIntake(
            lead_id=lead.id,
            description="Нужно проверить договор аренды офиса до подписания.",
            practice=Practice.hybrid,
            status=LegalIntakeStatus.accepted,
        )
        template = _template(name=f"Заготовка {name}", practice=Practice.hybrid, use_count=10_000)
        db.add_all([intake, template])
        db.commit()
        ids = {"lead_id": str(lead.id), "intake_id": str(intake.id), "template_id": str(template.id)}
    finally:
        db.close()
    yield {"name": name, "key": _key(Scope.admin, name), **ids}
    db = SessionLocal()
    try:
        db.execute(delete(AuditLog).where(AuditLog.target_id == ids["intake_id"]))
        db.execute(delete(AgreementTemplate).where(AgreementTemplate.id == ids["template_id"]))
        db.commit()
    finally:
        db.close()
    _cleanup([name], [ids["lead_id"]])
    get_settings.cache_clear()


def _stub(monkeypatch: pytest.MonkeyPatch, result: ChatResult, seen: list | None = None) -> None:
    def fake(messages, **kwargs):
        if seen is not None:
            seen.append({"messages": messages, **kwargs})
        return result

    monkeypatch.setattr(terms_draft, "chat", fake)


def test_endpoint_fills_the_form_from_the_most_used_template(monkeypatch, seeded) -> None:
    seen: list = []
    _stub(monkeypatch, ChatResult(text=_reply(), model="gpt-test", cost_usd=0.012), seen)
    response = TestClient(app).post(
        f"/api/v1/lawyer/intakes/{seeded['intake_id']}/terms-draft",
        headers={"X-API-Key": seeded["key"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["template"]["template_id"] == seeded["template_id"]
    assert body["fields"]["price_text"] == "15 000 ₽"
    assert body["amount_minor"] == 1_500_000
    assert body["notes"] == ["Уточнить, подписан ли договор"]
    assert seen[0]["response_format"] == {"type": "json_object"}
    assert "договор аренды офиса" in seen[0]["messages"][1]["content"]

    db = SessionLocal()
    try:
        audit = db.scalar(select(AuditLog).where(AuditLog.target_id == seeded["intake_id"]))
    finally:
        db.close()
    # В журнале — факт, модель и цена вызова; текста обращения нет.
    assert audit.action == "legal_intake.terms_draft"
    assert audit.details["cost_usd"] == 0.012 and audit.details["ok"] is True
    assert "договор" not in json.dumps(audit.details, ensure_ascii=False)


def test_endpoint_reports_a_failed_model_instead_of_an_empty_form(monkeypatch, seeded) -> None:
    _stub(monkeypatch, ChatResult(text="", model="gpt-test", error="timeout"))
    response = TestClient(app).post(
        f"/api/v1/lawyer/intakes/{seeded['intake_id']}/terms-draft",
        headers={"X-API-Key": seeded["key"]},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Model did not return a terms draft"


def test_endpoint_without_model_key_says_so(monkeypatch, seeded) -> None:
    monkeypatch.setenv("INTAKE_ANALYSIS_API_KEY", "")
    get_settings.cache_clear()
    _stub(monkeypatch, ChatResult(text=_reply(), model="gpt-test"))
    response = TestClient(app).post(
        f"/api/v1/lawyer/intakes/{seeded['intake_id']}/terms-draft",
        headers={"X-API-Key": seeded["key"]},
    )
    assert response.status_code == 503


def test_endpoint_is_for_the_lawyer_only(seeded) -> None:
    bot_name = f"{seeded['name']}.bot"
    try:
        response = TestClient(app).post(
            f"/api/v1/lawyer/intakes/{seeded['intake_id']}/terms-draft",
            headers={"X-API-Key": _key(Scope.bot, bot_name)},
        )
        assert response.status_code == 403
    finally:
        _cleanup([bot_name], [])
