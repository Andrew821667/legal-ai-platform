"""Сроки для календаря телефона.

Закрепляется: в календарь попадают срок по обращению, истечение отправленного
договора и срок оплаты акта — по московской дате; закрытое, архивное и
подписанное — нет; имени клиента в событиях нет (календарь уходит в облако).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    Lead,
    LeadSource,
    LegalIntake,
    LegalIntakeStatus,
    Scope,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)
from fastapi.testclient import TestClient

from test_client_archive import _agreement, _cleanup, _key


def test_calendar_lists_deadlines_without_client_names() -> None:
    now = datetime.now(timezone.utc)
    name = f"pytest.calendar.{uuid4().hex}"
    db = SessionLocal()
    try:
        lead = Lead(name="Секретный Клиентов", contact="secret@example.com", source=LeadSource.website_form)
        archived = Lead(name="Архивный", contact="arch@example.com", source=LeadSource.website_form, archived_at=now)
        db.add_all([lead, archived])
        db.flush()
        # 21:30 UTC — в Москве уже следующий день.
        late = (now + timedelta(days=5)).replace(hour=21, minute=30, second=0, microsecond=0)
        open_intake = LegalIntake(lead_id=lead.id, description="Открытое дело.", status=LegalIntakeStatus.accepted,
                                  deadline_at=late)
        closed_intake = LegalIntake(lead_id=lead.id, description="Закрытое дело.", status=LegalIntakeStatus.closed,
                                    deadline_at=now + timedelta(days=3))
        archived_intake = LegalIntake(lead_id=archived.id, description="Архив.", status=LegalIntakeStatus.accepted,
                                      deadline_at=now + timedelta(days=3))
        db.add_all([open_intake, closed_intake, archived_intake])
        db.flush()
        sent = _agreement(lead.id, open_intake.id, status=ServiceAgreementStatus.sent, signed_at=None,
                          sent_at=now, expires_at=now + timedelta(days=7))
        signed = _agreement(lead.id, open_intake.id, expires_at=now + timedelta(days=7))
        db.add_all([sent, signed])
        db.flush()
        act = WorkAct(act_number=f"AC-CAL-{uuid4().hex[:6].upper()}", agreement_id=signed.id, lead_id=lead.id,
                      description_text="Работа", amount_minor=100_000, status=WorkActStatus.sent,
                      sent_at=now - timedelta(days=2))
        db.add(act)
        db.commit()
        ids = {"lead": str(lead.id), "archived": str(archived.id), "intake": str(open_intake.id),
               "sent": str(sent.id), "signed": str(signed.id), "act": str(act.id), "number": sent.agreement_number,
               "act_number": act.act_number, "late": late}
    finally:
        db.close()
    try:
        response = TestClient(app).get("/api/v1/lawyer/calendar", headers={"X-API-Key": _key(Scope.admin, name)})
        assert response.status_code == 200, response.text
        mine = [e for e in response.json()["events"] if e["lead_id"] in (ids["lead"], ids["archived"])]
        by_uid = {e["uid"]: e for e in mine}
        assert set(by_uid) == {f"intake-{ids['intake']}", f"agreement-{ids['sent']}", f"act-{ids['act']}"}

        deadline = by_uid[f"intake-{ids['intake']}"]
        assert deadline["date"] == (ids["late"] + timedelta(hours=3)).date().isoformat()
        assert deadline["title"].startswith("Срок по делу:")
        assert ids["number"] in by_uid[f"agreement-{ids['sent']}"]["title"]
        assert by_uid[f"act-{ids['act']}"]["title"] == f"Срок оплаты: акт {ids['act_number']}"
        # Календарь уходит в облако — ни имени, ни контакта.
        text = str(mine)
        assert "Секретный" not in text and "secret@" not in text
    finally:
        _cleanup([name], [ids["lead"], ids["archived"]])
