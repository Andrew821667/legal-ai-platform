"""Журнал удалений: любое удаление дела клиента видно, удаление мимо приложения — владельцу.

Закрепляется: триггер пишет таблицу, id, клиента, пользователя БД и программу;
содержимого строки в журнале нет; удаление ядром не тревожит, удаление из
другой программы (psql, скрипт) — одно сообщение на транзакцию.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from core_api import deletion_log
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.models import ClientNotice, DeletionLog, Lead, LeadSource, LegalIntake, LegalIntakeStatus
from sqlalchemy import create_engine, delete, inspect, select, text


@pytest.fixture(autouse=True)
def clean_notices():
    yield
    db = SessionLocal()
    try:
        db.execute(delete(ClientNotice).where(ClientNotice.event_key.like("deletion:%")))
        db.commit()
    finally:
        db.close()


def _lead_with_intake() -> tuple[str, str]:
    db = SessionLocal()
    try:
        lead = Lead(name="Удаляемый", contact=f"del-{uuid4().hex[:6]}@example.com", source=LeadSource.website_form)
        db.add(lead)
        db.flush()
        intake = LegalIntake(lead_id=lead.id, description="Будет удалено.", status=LegalIntakeStatus.accepted)
        db.add(intake)
        db.commit()
        return str(lead.id), str(intake.id)
    finally:
        db.close()


def _log(row_id: str) -> DeletionLog | None:
    db = SessionLocal()
    try:
        return db.scalar(select(DeletionLog).where(DeletionLog.row_id == row_id))
    finally:
        db.close()


def test_app_deletion_is_logged_without_row_content_and_stays_quiet() -> None:
    lead_id, intake_id = _lead_with_intake()
    db = SessionLocal()
    try:
        db.execute(delete(LegalIntake).where(LegalIntake.id == intake_id))
        db.execute(delete(Lead).where(Lead.id == lead_id))
        db.commit()
    finally:
        db.close()
    entry = _log(intake_id)
    assert entry is not None
    assert entry.table_name == "legal_intakes"
    assert entry.lead_id == lead_id
    assert entry.application_name == deletion_log.APP_NAME
    # Только метаданные: ни описания, ни контактов.
    columns = {c["name"] for c in inspect(SessionLocal().get_bind()).get_columns("deletion_log")}
    assert columns == {"id", "table_name", "row_id", "lead_id", "deleted_at", "db_user", "application_name", "client_addr", "txid"}

    deletion_log.watch()
    db = SessionLocal()
    try:
        assert db.scalar(select(ClientNotice).where(ClientNotice.event_key.like("deletion:%"))) is None
    finally:
        db.close()


def test_deletion_outside_the_app_reaches_the_owner_once() -> None:
    lead_id, intake_id = _lead_with_intake()
    outsider = create_engine(get_settings().database_url, connect_args={"application_name": "psql"})
    with outsider.begin() as conn:
        conn.execute(text("DELETE FROM legal_intakes WHERE id = :id"), {"id": intake_id})
        conn.execute(text("DELETE FROM leads WHERE id = :id"), {"id": lead_id})
    outsider.dispose()

    assert _log(intake_id).application_name == "psql"
    deletion_log.watch()
    deletion_log.watch()
    db = SessionLocal()
    try:
        texts = list(db.scalars(select(ClientNotice.text).where(ClientNotice.event_key.like("deletion:%"))))
    finally:
        db.close()
    assert len(texts) == 1
    assert "обращения — 1" in texts[0] and "клиенты — 1" in texts[0] and "psql" in texts[0]
