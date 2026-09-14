from uuid import uuid4

from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ConflictCheckStatus, Lead, Practice, Scope
from fastapi.testclient import TestClient
from test_practice import _cleanup, _key, _seed


def test_repeat_case_reuses_only_verified_identity(monkeypatch):
    from core_api.routers import legal_intakes

    monkeypatch.setattr(legal_intakes, "notify_new_legal_intake", lambda *_: None)
    names = [f"pytest.client-cases.{uuid4().hex}"]
    key = _key(Scope.bot, names[0])
    client = TestClient(app)
    body = {
        "source": "telegram_bot", "telegram_user_id": int(uuid4().hex[:10], 16),
        "name": "Test Client", "contact": "test@example.invalid",
        "description": "A separate task with its own scope and documents",
        "consent_accepted": True, "consent_version": "test",
        "consent_at": "2026-09-13T00:00:00Z",
    }
    leads = set()
    try:
        results = []
        for _ in range(2):
            result = client.post("/api/v1/legal-intakes", json=body, headers={"X-API-Key": key})
            assert result.status_code == 201, result.text
            results.append(result.json())
            leads.add(result.json()["lead_id"])
        assert results[0]["id"] != results[1]["id"]
        assert results[0]["lead_id"] == results[1]["lead_id"]
        body.pop("telegram_user_id")
        body["source"] = "website_form"
        for _ in range(2):
            result = client.post("/api/v1/legal-intakes", json=body, headers={"X-API-Key": key})
            assert result.status_code == 201
            assert result.json()["lead_id"] not in leads
            leads.add(result.json()["lead_id"])
    finally:
        for lead_id in leads:
            _cleanup([], lead_id)
        _cleanup(names, None)


def test_without_agreement_keeps_case_open_and_respects_gates():
    names = [f"pytest.case-no-agreement.{uuid4().hex}"]
    key = _key(Scope.admin, names[0])
    client = TestClient(app)
    for practice, nda, conflict, expected in (
        (Practice.engineering, False, ConflictCheckStatus.unchecked, 409),
        (Practice.engineering, True, ConflictCheckStatus.unchecked, 200),
        (Practice.legal, True, ConflictCheckStatus.unchecked, 409),
        (Practice.legal, True, ConflictCheckStatus.clear, 200),
    ):
        seed = _seed(practice=practice, nda=nda, conflict=conflict)
        try:
            result = client.patch(f"/api/v1/legal-intakes/{seed['intake_id']}",
                                  headers={"X-API-Key": key}, json={"without_agreement": True})
            assert result.status_code == expected, result.text
            if expected == 200:
                assert result.json()["without_agreement"] is True
                assert result.json()["status"] == "accepted"
                with SessionLocal() as db:
                    assert db.get(Lead, seed["lead_id"]).status.value == "won"
        finally:
            _cleanup([], seed["lead_id"])
    _cleanup(names, None)


def test_documents_require_real_nda_not_client_flag():
    names = [f"pytest.case-documents.{uuid4().hex}"]
    key = _key(Scope.bot, names[0])
    seed = _seed(practice=Practice.engineering, nda=False, conflict=ConflictCheckStatus.unchecked)
    try:
        result = TestClient(app).post(f"/api/v1/legal-intakes/{seed['intake_id']}/documents",
            headers={"X-API-Key": key}, json={"telegram_file_id": "test", "nda_signed_at_upload": True})
        assert result.status_code == 409
    finally:
        _cleanup(names, seed["lead_id"])
