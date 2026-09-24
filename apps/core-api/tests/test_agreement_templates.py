"""Заготовки условий договора: создать, найти по практике, поднять частые, удалить."""

from __future__ import annotations

from uuid import uuid4

from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import AgreementTemplate, Scope
from fastapi.testclient import TestClient
from sqlalchemy import delete

from test_client_archive import _cleanup, _key

BODY = {
    "name": "Проверка договора",
    "practice": "legal",
    "subject": "Правовой анализ договора",
    "scope_text": "Изучить договор и подготовить письменные замечания",
    "exclusions_text": "Переговоры с контрагентом",
    "schedule_text": "Три рабочих дня",
    "price_text": "15 000 ₽",
    "amount_minor": 1_500_000,
    "payment_terms": "100% до начала работы",
}


def test_templates_by_practice_most_used_first() -> None:
    client = TestClient(app)
    name = f"pytest.templates.{uuid4().hex}"
    headers = {"X-API-Key": _key(Scope.admin, name)}
    try:
        legal = client.post("/api/v1/lawyer/agreement-templates", headers=headers, json=BODY)
        assert legal.status_code == 201, legal.text
        common = client.post(
            "/api/v1/lawyer/agreement-templates",
            headers=headers,
            json={**BODY, "name": "Консультация", "practice": None},
        ).json()
        client.post(
            "/api/v1/lawyer/agreement-templates",
            headers=headers,
            json={**BODY, "name": "Разработка бота", "practice": "engineering"},
        )

        names = [t["name"] for t in client.get("/api/v1/lawyer/agreement-templates?practice=legal", headers=headers).json()]
        # Для права — свои и общие, инженерной заготовки нет.
        assert set(names) >= {"Проверка договора", "Консультация"}
        assert "Разработка бота" not in names

        client.post(f"/api/v1/lawyer/agreement-templates/{common['template_id']}/used", headers=headers)
        first = client.get("/api/v1/lawyer/agreement-templates?practice=legal", headers=headers).json()[0]
        assert first["name"] == "Консультация"

        updated = client.put(
            f"/api/v1/lawyer/agreement-templates/{common['template_id']}",
            headers=headers,
            json={**BODY, "name": "Консультация  ", "price_text": "5 000 ₽", "practice": None},
        ).json()
        assert updated["name"] == "Консультация"
        assert updated["price_text"] == "5 000 ₽"

        gone = client.delete(f"/api/v1/lawyer/agreement-templates/{common['template_id']}", headers=headers)
        assert gone.status_code == 200
        assert client.delete(f"/api/v1/lawyer/agreement-templates/{common['template_id']}", headers=headers).status_code == 404

        too_long = client.post(
            "/api/v1/lawyer/agreement-templates", headers=headers, json={**BODY, "price_text": "x" * 501}
        )
        assert too_long.status_code == 422
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(AgreementTemplate))
            db.commit()
        finally:
            db.close()
        _cleanup([name], [])
