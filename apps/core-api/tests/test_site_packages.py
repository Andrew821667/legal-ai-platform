"""Пакеты услуг с сайта: обращение приходит с ценой, договор — из заготовки.

Закрепляется: пакет сохраняется в обращении снимком (что клиент видел);
карточка юриста показывает пакет и заготовку под него; у пакета не бывает
двух заготовок; без пакета название и цена не сохраняются.
"""

from __future__ import annotations

from uuid import uuid4

from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import AgreementTemplate, LegalIntake, Scope
from fastapi.testclient import TestClient
from sqlalchemy import delete

from test_practice import _cleanup, _key

PACKAGE = "legal_contract_review"


def _body(**kwargs) -> dict:
    body = {
        "source": "website_form",
        "name": "Пакетный клиент",
        "contact": f"pkg-{uuid4().hex[:8]}@example.com",
        "description": "Нужно проверить договор поставки перед подписанием.",
        "consent_accepted": True,
        "consent_version": "test",
        "consent_at": "2026-09-26T00:00:00Z",
        "package_id": PACKAGE,
        "package_title": "Экспресс-проверка договора",
        "package_price_text": "от 7 900 ₽",
    }
    body.update(kwargs)
    return body


def _template_body(**kwargs) -> dict:
    body = {
        "name": f"Проверка договора {uuid4().hex[:6]}",
        "practice": "legal",
        "subject": "Правовой анализ договора",
        "scope_text": "Изучить договор и подготовить замечания",
        "exclusions_text": "Переговоры",
        "schedule_text": "Три рабочих дня",
        "price_text": "7 900 ₽",
        "amount_minor": 790_000,
        "payment_terms": "100% до начала работы",
        "package_id": PACKAGE,
    }
    body.update(kwargs)
    return body


def _drop_templates(ids: list[str]) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(AgreementTemplate).where(AgreementTemplate.id.in_(ids)))
        db.commit()
    finally:
        db.close()


def test_package_reaches_the_lawyer_card_with_its_template(monkeypatch) -> None:
    from core_api.routers import legal_intakes

    monkeypatch.setattr(legal_intakes, "notify_new_legal_intake", lambda *_: None)
    names = [f"pytest.packages.{uuid4().hex}", f"pytest.packages.admin.{uuid4().hex}"]
    bot = {"X-API-Key": _key(Scope.bot, names[0])}
    admin = {"X-API-Key": _key(Scope.admin, names[1])}
    client = TestClient(app)
    lead_id = None
    templates: list[str] = []
    try:
        created = client.post("/api/v1/legal-intakes", json=_body(), headers=bot)
        assert created.status_code == 201, created.text
        lead_id = created.json()["lead_id"]

        card = client.get(f"/api/v1/lawyer/clients/{lead_id}", headers=admin).json()
        package = card["intakes"][0]["package"]
        # Заготовки под пакет пока нет — юрист увидит пакет и цену, форма пустая.
        assert package == {
            "id": PACKAGE,
            "title": "Экспресс-проверка договора",
            "price_text": "от 7 900 ₽",
            "template_id": None,
        }

        template = client.post("/api/v1/lawyer/agreement-templates", json=_template_body(), headers=admin)
        assert template.status_code == 201, template.text
        templates.append(template.json()["template_id"])
        assert template.json()["package_id"] == PACKAGE

        card = client.get(f"/api/v1/lawyer/clients/{lead_id}", headers=admin).json()
        assert card["intakes"][0]["package"]["template_id"] == templates[0]

        # Вторая заготовка на тот же пакет — отказ, а не гадание формы.
        twin = client.post("/api/v1/lawyer/agreement-templates", json=_template_body(), headers=admin)
        assert twin.status_code == 409
        assert twin.json()["detail"] == "Package already has a template"

        # Отвязать можно — тогда пакет свободен для другой заготовки.
        cleared = client.put(
            f"/api/v1/lawyer/agreement-templates/{templates[0]}",
            json=_template_body(name="Без пакета", package_id=None),
            headers=admin,
        )
        assert cleared.status_code == 200 and cleared.json()["package_id"] is None
        again = client.post("/api/v1/lawyer/agreement-templates", json=_template_body(), headers=admin)
        assert again.status_code == 201
        templates.append(again.json()["template_id"])
    finally:
        _drop_templates(templates)
        _cleanup(names, lead_id)


def test_without_package_title_and_price_are_not_kept(monkeypatch) -> None:
    from core_api.routers import legal_intakes

    monkeypatch.setattr(legal_intakes, "notify_new_legal_intake", lambda *_: None)
    names = [f"pytest.packages.none.{uuid4().hex}"]
    bot = {"X-API-Key": _key(Scope.bot, names[0])}
    client = TestClient(app)
    lead_id = None
    try:
        created = client.post("/api/v1/legal-intakes", json=_body(package_id=None), headers=bot)
        assert created.status_code == 201, created.text
        lead_id = created.json()["lead_id"]
        db = SessionLocal()
        try:
            intake = db.get(LegalIntake, created.json()["id"])
            assert (intake.package_id, intake.package_title, intake.package_price_text) == (None, None, None)
        finally:
            db.close()

        bad = client.post("/api/v1/legal-intakes", json=_body(package_id="../etc"), headers=bot)
        assert bad.status_code == 422
    finally:
        _cleanup(names, lead_id)
