"""Лиды только в ядре: перенос старых строк, лид для обращения, транспорт."""

from __future__ import annotations

import os
import tempfile
import urllib.error

import pytest

import core_leads
from database import Database
from tests.fake_core import FakeCore, install as install_fake_core


@pytest.fixture
def test_db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(db_path)
    yield db
    if os.path.exists(db_path):
        os.unlink(db_path)


def _insert_legacy_lead(db: Database, user_id: int, lead_id: int, **fields) -> None:
    """Строка старой таблицы — такой её оставила прежняя версия бота."""
    columns = ["id", "user_id", *fields.keys()]
    conn = db.get_connection()
    try:
        conn.execute(
            f"INSERT INTO leads ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            [lead_id, user_id, *fields.values()],
        )
        conn.commit()
    finally:
        conn.close()


def test_handover_links_claims_and_creates_without_overwriting(test_db, monkeypatch):
    core = install_fake_core(monkeypatch, test_db)
    linked_user = test_db.create_or_update_user(telegram_id=9001, first_name="Уже в ядре")
    claim_user = test_db.create_or_update_user(telegram_id=9002, first_name="Через обращение")
    fresh_user = test_db.create_or_update_user(telegram_id=9003, first_name="Только в SQLite")

    # 1. Лид, который прежняя версия успела отразить в ядре: там юрист уже
    #    поменял статус — переносить содержимое нельзя.
    core.leads.append(core._new_lead({"legacy_lead_id": 3, "telegram_user_id": 9001, "name": "Из ядра", "status": "won"}))
    _insert_legacy_lead(test_db, linked_user, 3, name="Старое имя", status="new", temperature="cold")
    # 2. Лид, заведённый обращением: в ядре есть, номера нет.
    core.leads.append(core._new_lead({"legacy_lead_id": None, "telegram_user_id": 9002, "name": "Клиент обращения", "status": "qualified"}))
    core.leads[-1]["legacy_lead_id"] = None
    _insert_legacy_lead(test_db, claim_user, 7, name="Локальная копия", temperature="warm", notes="[LEGAL_HELP] client_type=individual")
    # 3. Лид, которого в ядре нет вовсе.
    _insert_legacy_lead(
        test_db, fresh_user, 25, name="Пётр", email="p@example.ru", temperature="hot",
        pain_point="Спор с подрядчиком", created_at="2026-05-31 10:00:00", cta_shown=1,
    )

    summary = test_db.handover_leads_to_core()

    assert summary == {"local": 3, "linked": 1, "created": 2, "failed": 0, "next_id": 26}
    by_legacy = {row["legacy_lead_id"]: row for row in core.leads}
    assert by_legacy[3]["name"] == "Из ядра" and by_legacy[3]["status"] == "won"
    assert by_legacy[7]["name"] == "Клиент обращения" and by_legacy[7]["status"] == "qualified"
    assert by_legacy[25]["email"] == "p@example.ru"
    assert by_legacy[25]["created_at"] == "2026-05-31 10:00:00"
    assert by_legacy[25]["cta_shown"] is True
    assert len(core.leads) == 3
    assert core.next_legacy_id == 26

    conn = test_db.get_connection()
    marked = {row[0]: row[1] for row in conn.execute("SELECT id, core_lead_id FROM leads")}
    conn.close()
    assert marked == {3: by_legacy[3]["id"], 7: by_legacy[7]["id"], 25: by_legacy[25]["id"]}

    # Повторный запуск ничего не переносит и не двигает счётчик.
    calls_before = len(core.calls)
    again = test_db.handover_leads_to_core()
    assert (again["linked"], again["created"], again["failed"]) == (0, 0, 0)
    assert len(core.calls) == calls_before

    # Новый лид получает номер после старых.
    new_user = test_db.create_or_update_user(telegram_id=9004, first_name="Новый")
    assert test_db.create_or_update_lead(new_user, {"name": "Новый"}) == 26


def test_handover_retries_rows_left_behind_when_core_was_down(test_db, monkeypatch):
    core = install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(telegram_id=9010, first_name="Позже")
    _insert_legacy_lead(test_db, user_id, 5, name="Позже", temperature="warm")

    core.down = True
    first = test_db.handover_leads_to_core()
    assert first["failed"] == 1 and first["created"] == 0

    core.down = False
    second = test_db.handover_leads_to_core()
    assert second["created"] == 1 and second["failed"] == 0


def test_record_intake_lead_updates_the_lead_the_intake_attached_to(test_db, monkeypatch):
    core = install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(telegram_id=9020, username="client", first_name="Анна")
    # Обращение уже завело лид в ядре (с номером — его выдаёт ядро).
    core.leads.append(core._new_lead({"telegram_user_id": 9020, "name": "Анна", "conversation_stage": "legal_intake"}))
    core_id = core.leads[0]["id"]

    lead_id = test_db.record_intake_lead(user_id, core_id, {"temperature": "warm", "cta_variant": "legal_help", "cta_shown": 1})

    assert lead_id == core.leads[0]["legacy_lead_id"]
    assert len(core.leads) == 1
    assert core.leads[0]["temperature"] == "warm"
    assert core.leads[0]["cta_variant"] == "legal_help"
    assert core.leads[0]["conversation_stage"] == "legal_intake"

    # Без подтверждённого обращения лид заводится сам, чтобы человек не пропал.
    fallback_id = test_db.record_intake_lead(user_id, None, {"name": "Анна", "pain_point": "Спор", "temperature": "warm"})
    assert fallback_id != lead_id
    assert len(core.leads) == 2

    core.down = True
    assert test_db.record_intake_lead(user_id, None, {"name": "Анна"}) is None


def test_touching_a_missing_lead_is_not_an_error(test_db, monkeypatch):
    core = install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(telegram_id=9030, first_name="Без лида")

    test_db.update_lead_last_message_time(user_id)
    test_db.update_lead_funnel_state(user_id, conversation_stage="diagnose")

    assert core.leads == []


def test_payload_mapping_from_legacy_fields():
    assert core_leads.CoreLeadStore.payload_from_legacy({"status": "qualified"}) == {"status": "qualified"}
    # «new» от бота не отправляется: статус двигает юрист, и «new» его откатывал бы.
    assert core_leads.CoreLeadStore.payload_from_legacy({"status": "new"}) == {}
    payload = core_leads.CoreLeadStore.payload_from_legacy(
        {
            "name": "Иван",
            "lead_temperature": "hot",
            "status": "converted",
            "cta_shown": 1,
            "lead_magnet_delivered": 0,
            "notes": "x" * 5000,
            "user_id": 5,
            "email": None,
            "team_size": "6-20",
        }
    )
    assert payload == {
        "name": "Иван",
        "temperature": "hot",
        "cta_shown": True,
        "lead_magnet_delivered": False,
        "notes": "x" * 4000,
        "team_size": "6-20",
    }


def test_http_transport_retries_network_errors_then_gives_up(monkeypatch):
    attempts: list[str] = []
    monkeypatch.setattr(core_leads.time, "sleep", lambda _seconds: None)

    def _urlopen(request, timeout):
        attempts.append(request.full_url)
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(core_leads.urllib.request, "urlopen", _urlopen)
    transport = core_leads.HttpCoreTransport("http://core.test", "key", 1.0)

    with pytest.raises(core_leads.LeadStoreError):
        transport.post("/api/v1/leads", {"source": "telegram_bot"})
    assert len(attempts) == 4


def test_http_transport_treats_404_as_absent_and_other_errors_as_failures(monkeypatch):
    def _urlopen(request, timeout):
        code = 404 if request.full_url.endswith("/missing") else 500
        raise urllib.error.HTTPError(request.full_url, code, "err", hdrs=None, fp=None)

    monkeypatch.setattr(core_leads.urllib.request, "urlopen", _urlopen)
    transport = core_leads.HttpCoreTransport("http://core.test", "key", 1.0)

    assert transport.get("/missing") is None
    with pytest.raises(core_leads.LeadStoreError):
        transport.get("/broken")
