"""Проверочные заявки после деплоя не становятся клиентами.

Закрепляется: заявка с «smoke» в utm создаётся по-настоящему, но сразу в
архиве с пометкой [SMOKE] и без уведомления юристу; обычная — как раньше.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from core_api import smoke
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import Lead, LegalIntake, Scope
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_client_archive import _cleanup, _key


@pytest.mark.parametrize(
    ("values", "expected"),
    [(("smoke", None, None), True), ((None, "Deploy_Smoke", None), True), (("prod_smoke", "x", None), True),
     (("telegram", "channel", "spring"), False), ((None, None, None), False)],
)
def test_is_smoke(values, expected) -> None:
    assert smoke.is_smoke(*values) is expected


@pytest.fixture
def notified(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    import core_api.routers.leads as leads_router
    import core_api.routers.legal_intakes as intakes_router

    calls: list[str] = []
    monkeypatch.setattr(leads_router, "notify_new_lead", lambda lead_id: calls.append(f"lead:{lead_id}"))
    monkeypatch.setattr(intakes_router, "notify_new_legal_intake", lambda item_id: calls.append(f"intake:{item_id}"))
    return calls


def _lead(lead_id: str) -> Lead:
    db = SessionLocal()
    try:
        return db.get(Lead, lead_id)
    finally:
        db.close()


def test_smoke_website_lead_is_archived_and_silent(notified) -> None:
    name = f"pytest.smoke.{uuid4().hex}"
    headers = {"X-API-Key": _key(Scope.bot, name)}
    client = TestClient(app)
    created: list[str] = []
    try:
        smoke_lead = client.post(
            "/api/v1/leads",
            json={"source": "website_form", "name": "Проверка", "contact": f"smoke-{uuid4().hex}@example.com",
                  "utm_source": "smoke", "utm_medium": "deploy"},
            headers=headers,
        ).json()
        real = client.post(
            "/api/v1/leads",
            json={"source": "website_form", "name": "Клиент", "contact": f"real-{uuid4().hex}@example.com",
                  "utm_source": "yandex"},
            headers=headers,
        ).json()
        created += [smoke_lead["id"], real["id"]]
        assert _lead(smoke_lead["id"]).archived_at is not None
        assert _lead(smoke_lead["id"]).notes.startswith(smoke.MARK)
        assert _lead(real["id"]).archived_at is None
        assert notified == [f"lead:{real['id']}"]
    finally:
        _cleanup([name], created)


def test_smoke_legal_intake_is_archived_and_silent(notified) -> None:
    name = f"pytest.smoke.intake.{uuid4().hex}"
    headers = {"X-API-Key": _key(Scope.bot, name)}
    response = TestClient(app).post(
        "/api/v1/legal-intakes",
        headers=headers,
        json={
            "source": "website_form",
            "name": "Проверка",
            "contact": "smoke@example.com",
            "client_type": "individual",
            "legal_area": "disputes",
            "description": "Проверочная заявка после деплоя.",
            "urgency": "normal",
            "consent_accepted": True,
            "consent_version": "pytest-v1",
            "consent_at": "2026-09-24T10:00:00Z",
            "utm_source": "prod_smoke",
        },
    )
    lead_id = response.json().get("lead_id")
    try:
        assert response.status_code == 201, response.text
        lead = _lead(lead_id)
        assert lead.archived_at is not None and lead.notes.startswith(smoke.MARK)
        db = SessionLocal()
        try:
            assert db.scalar(select(LegalIntake.id).where(LegalIntake.lead_id == lead_id)) is not None
        finally:
            db.close()
        assert notified == []
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(LegalIntake).where(LegalIntake.lead_id == lead_id))
            db.commit()
        finally:
            db.close()
        _cleanup([name], [lead_id] if lead_id else [])
