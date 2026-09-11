"""Рабочее место юриста.

Главное, что здесь закрепляется: экран «Сегодня» показывает застрявшее, а не
всё подряд. Список всех дел не отвечает на вопрос «что стоит из-за меня», и
именно ради этого ответа экран заводился.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    Lead,
    LegalIntake,
    LeadSource,
    LegalIntakeStatus,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
    ServiceAgreementStatus,
)
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete


def _key(name: str) -> str:
    raw = generate_api_key()
    db = SessionLocal()
    try:
        db.add(ApiKey(key_hash=hash_api_key(raw), scope=Scope.admin, name=name, is_active=True))
        db.commit()
        cache.invalidate()
    finally:
        db.close()
    return raw


def _agreement(**kwargs) -> ServiceAgreement:
    defaults = dict(
        agreement_number=f"A-{datetime.now(timezone.utc).timestamp()}",
        subject="Раздел имущества",
        scope_text="",
        exclusions_text="",
        schedule_text="",
        price_text="80 000 ₽",
        payment_terms="",
        operator_snapshot={},
        client_snapshot={},
        document_text="текст",
        document_version="v1",
        document_hash="h" * 64,
        status=ServiceAgreementStatus.draft,
    )
    defaults.update(kwargs)
    return ServiceAgreement(**defaults)


def _seed() -> dict:
    """Клиент с обращением и черновиком, который не ушёл."""
    db = SessionLocal()
    try:
        lead = Lead(name="Рябов Александр", contact="@ryabov", source=LeadSource.telegram_bot)
        db.add(lead)
        db.flush()
        intake = LegalIntake(
            lead_id=lead.id,
            description="Раздел квартиры в ипотеке после развода.",
            status=LegalIntakeStatus.scope_preparation,
        )
        db.add(intake)
        db.flush()
        agreement = _agreement(lead_id=lead.id, intake_id=intake.id)
        db.add(agreement)
        db.commit()
        return {"lead_id": str(lead.id), "intake_id": str(intake.id), "agreement_id": str(agreement.id)}
    finally:
        db.close()


def _cleanup(keys: list[str], lead_id: str) -> None:
    db = SessionLocal()
    try:
        ids = db.execute(
            delete(ServiceAgreement).where(ServiceAgreement.lead_id == lead_id).returning(ServiceAgreement.id)
        ).scalars().all()
        if ids:
            db.execute(delete(ServiceAgreementMessage).where(ServiceAgreementMessage.agreement_id.in_(ids)))
        db.execute(delete(NdaSignature).where(NdaSignature.lead_id == lead_id))
        db.execute(delete(LegalIntake).where(LegalIntake.lead_id == lead_id))
        db.execute(delete(Lead).where(Lead.id == lead_id))
        db.execute(delete(ApiKey).where(ApiKey.name.in_(keys)))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def _section(body: dict, key: str) -> dict:
    return next(s for s in body["sections"] if s["key"] == key)


def test_today_surfaces_the_unsent_draft() -> None:
    """Самая обидная задержка: работа сделана, а клиент ждёт и не знает почему."""
    client = TestClient(app)
    names = ["pytest.workspace.today"]
    key = _key(names[0])
    seeded = _seed()
    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        drafts = _section(body, "draft_not_sent")["items"]
        mine = [d for d in drafts if d["agreement_id"] == seeded["agreement_id"]]
        assert len(mine) == 1
        assert mine[0]["client"] == "Рябов Александр"
        assert mine[0]["price_text"] == "80 000 ₽"
        assert mine[0]["days_waiting"] is not None
    finally:
        _cleanup(names, seeded["lead_id"])


def test_today_flags_an_unanswered_client_question() -> None:
    """Последнее слово за клиентом — значит очередь наша."""
    client = TestClient(app)
    names = ["pytest.workspace.question"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        db.add(
            ServiceAgreementMessage(
                agreement_id=seeded["agreement_id"],
                role=ServiceAgreementMessageRole.client,
                text="А госпошлина входит в стоимость?",
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        items = _section(body, "client_question")["items"]
        assert any("госпошлина" in i["question"] for i in items)
    finally:
        _cleanup(names, seeded["lead_id"])


def test_answered_question_leaves_the_queue() -> None:
    """Ответили — задача уходит с экрана, иначе он перестаёт быть списком дел."""
    client = TestClient(app)
    names = ["pytest.workspace.answered"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        base = datetime.now(timezone.utc)
        db.add(
            ServiceAgreementMessage(
                agreement_id=seeded["agreement_id"],
                role=ServiceAgreementMessageRole.client,
                text="Вопрос",
                created_at=base - timedelta(hours=2),
            )
        )
        db.add(
            ServiceAgreementMessage(
                agreement_id=seeded["agreement_id"],
                role=ServiceAgreementMessageRole.lawyer,
                text="Ответ",
                created_at=base,
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        items = _section(body, "client_question")["items"]
        assert not any(i["agreement_id"] == seeded["agreement_id"] for i in items)
    finally:
        _cleanup(names, seeded["lead_id"])


def test_unreachable_client_is_shown() -> None:
    """Бот не может написать первым — нужен человек."""
    client = TestClient(app)
    names = ["pytest.workspace.unreachable"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        intake = db.get(LegalIntake, seeded["intake_id"])
        intake.outreach_blocked_reason = "no_telegram"
        db.add(intake)
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        items = _section(body, "unreachable")["items"]
        assert any(i["intake_id"] == seeded["intake_id"] and i["reason"] == "no_telegram" for i in items)
    finally:
        _cleanup(names, seeded["lead_id"])


def test_expiring_offer_is_surfaced_before_it_lapses() -> None:
    """Статус «истёк» ставится, только когда клиент откроет просрочку.

    То есть о сгорающем сроке юристу узнать неоткуда, а когда узнает — уже
    поздно: редакцию придётся составлять заново.
    """
    client = TestClient(app)
    names = ["pytest.workspace.expiring"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        agreement = db.get(ServiceAgreement, seeded["agreement_id"])
        agreement.status = ServiceAgreementStatus.sent
        agreement.sent_at = datetime.now(timezone.utc) - timedelta(days=6)
        agreement.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        mine = [
            i
            for i in _section(body, "expiring")["items"]
            if i["agreement_id"] == seeded["agreement_id"]
        ]
        assert len(mine) == 1
        assert mine[0]["days_left"] == 0
        assert mine[0]["expires_at"] is not None

        # И не задваивается в «клиент молчит»: дело одно, а задача — другая.
        silent = _section(body, "awaiting_client")["items"]
        assert not [i for i in silent if i["agreement_id"] == seeded["agreement_id"]]
    finally:
        _cleanup(names, seeded["lead_id"])


def test_lapsed_offer_counts_down_past_zero() -> None:
    """Просроченное предложение не исчезает: пока клиент его не открыл, оно
    висит в «отправлен» и требует решения."""
    client = TestClient(app)
    names = ["pytest.workspace.lapsed"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        agreement = db.get(ServiceAgreement, seeded["agreement_id"])
        agreement.status = ServiceAgreementStatus.sent
        agreement.sent_at = datetime.now(timezone.utc) - timedelta(days=10)
        agreement.expires_at = datetime.now(timezone.utc) - timedelta(days=2)
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        mine = [
            i
            for i in _section(body, "expiring")["items"]
            if i["agreement_id"] == seeded["agreement_id"]
        ]
        assert len(mine) == 1
        assert mine[0]["days_left"] < 0
    finally:
        _cleanup(names, seeded["lead_id"])


def test_offer_with_room_left_stays_out_of_the_expiring_list() -> None:
    """Иначе раздел «истекает» превратится в список всех отправленных."""
    client = TestClient(app)
    names = ["pytest.workspace.roomy"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        agreement = db.get(ServiceAgreement, seeded["agreement_id"])
        agreement.status = ServiceAgreementStatus.sent
        agreement.sent_at = datetime.now(timezone.utc)
        agreement.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        items = _section(body, "expiring")["items"]
        assert not [i for i in items if i["agreement_id"] == seeded["agreement_id"]]
    finally:
        _cleanup(names, seeded["lead_id"])


def test_intake_deadline_reaches_the_task_screen() -> None:
    """Слова клиента о сроке лежат в тексте и напоминанием стать не могут.

    Дату юрист ставит сам — и вот она уже должна поднимать дело на экран.
    """
    client = TestClient(app)
    names = ["pytest.workspace.deadline"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        intake = db.get(LegalIntake, seeded["intake_id"])
        intake.deadline = "к этому четвергу"
        intake.deadline_at = datetime.now(timezone.utc) + timedelta(days=1)
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        mine = [
            i
            for i in _section(body, "deadline_soon")["items"]
            if i["intake_id"] == seeded["intake_id"]
        ]
        assert len(mine) == 1
        assert mine[0]["days_left"] == 0

        card = client.get(
            f"/api/v1/lawyer/clients/{seeded['lead_id']}", headers={"X-API-Key": key}
        ).json()
        # Слова клиента остаются нетронутыми рядом с датой.
        assert card["intakes"][0]["deadline"] == "к этому четвергу"
        assert card["intakes"][0]["deadline_at"] is not None
    finally:
        _cleanup(names, seeded["lead_id"])


def test_intake_without_a_date_stays_off_the_task_screen() -> None:
    """Иначе раздел наполнился бы всеми обращениями сразу."""
    client = TestClient(app)
    names = ["pytest.workspace.nodeadline"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        intake = db.get(LegalIntake, seeded["intake_id"])
        # Срок словами есть, даты нет — напоминать не по чему.
        intake.deadline = "как получится"
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        items = _section(body, "deadline_soon")["items"]
        assert not [i for i in items if i["intake_id"] == seeded["intake_id"]]
    finally:
        _cleanup(names, seeded["lead_id"])


def test_far_deadline_waits_its_turn() -> None:
    client = TestClient(app)
    names = ["pytest.workspace.fardeadline"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        intake = db.get(LegalIntake, seeded["intake_id"])
        intake.deadline_at = datetime.now(timezone.utc) + timedelta(days=30)
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        items = _section(body, "deadline_soon")["items"]
        assert not [i for i in items if i["intake_id"] == seeded["intake_id"]]
    finally:
        _cleanup(names, seeded["lead_id"])


def test_client_card_gathers_everything_in_one_answer() -> None:
    """Карточку открывают, чтобы вспомнить контекст перед разговором."""
    client = TestClient(app)
    names = ["pytest.workspace.card"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        db.add(
            NdaSignature(
                lead_id=seeded["lead_id"],
                signer_full_name="Рябов Александр Алексеевич",
                signer_contact="+79000000000",
                document_version="v1",
                document_hash="n" * 64,
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        card = client.get(
            f"/api/v1/lawyer/clients/{seeded['lead_id']}", headers={"X-API-Key": key}
        ).json()
        assert card["nda"]["signer_full_name"] == "Рябов Александр Алексеевич"
        assert len(card["intakes"]) == 1
        assert "ипотеке" in card["intakes"][0]["description"]
        assert len(card["agreements"]) == 1
        assert card["agreements"][0]["status"] == "draft"
        # По какому обращению договор — без этого при втором обращении клиента
        # на экране не разобрать, к чему он относится.
        assert card["agreements"][0]["intake_id"] == seeded["intake_id"]
    finally:
        _cleanup(names, seeded["lead_id"])


def test_decline_reason_reaches_the_card() -> None:
    """Клиент называет причину, когда отклоняет. Раньше юрист видел только дату."""
    client = TestClient(app)
    names = ["pytest.workspace.decline"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        agreement = db.get(ServiceAgreement, seeded["agreement_id"])
        agreement.status = ServiceAgreementStatus.declined
        agreement.declined_at = datetime.now(timezone.utc)
        agreement.decline_reason = "Дорого, буду искать другого юриста"
        db.commit()
    finally:
        db.close()

    try:
        card = client.get(
            f"/api/v1/lawyer/clients/{seeded['lead_id']}", headers={"X-API-Key": key}
        ).json()
        assert card["agreements"][0]["decline_reason"] == "Дорого, буду искать другого юриста"
    finally:
        _cleanup(names, seeded["lead_id"])


def test_signed_text_is_available_on_demand() -> None:
    """Условия в карточке — реконструкция по полям. При споре нужен сам документ.

    Хеш — то, под чем клиент поставил подпись; без текста рядом он ничего не
    доказывает, поэтому отдаются вместе.
    """
    client = TestClient(app)
    names = ["pytest.workspace.doc"]
    key = _key(names[0])
    seeded = _seed()
    try:
        body = client.get(
            f"/api/v1/lawyer/agreements/{seeded['agreement_id']}/document",
            headers={"X-API-Key": key},
        ).json()
        assert body["document_text"] == "текст"
        assert body["document_hash"] == "h" * 64
        assert body["document_version"] == "v1"

        # Полный текст не должен раздувать карточку — там его нет.
        card = client.get(
            f"/api/v1/lawyer/clients/{seeded['lead_id']}", headers={"X-API-Key": key}
        ).json()
        assert "document_text" not in card["agreements"][0]
    finally:
        _cleanup(names, seeded["lead_id"])


def test_nda_text_is_available_on_demand() -> None:
    client = TestClient(app)
    names = ["pytest.workspace.ndadoc"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        nda = NdaSignature(
            lead_id=seeded["lead_id"],
            signer_full_name="Рябов Александр",
            document_version="v3",
            document_hash="n" * 64,
            document_text="Соглашение о конфиденциальности, редакция 3",
        )
        db.add(nda)
        db.commit()
        nda_id = str(nda.id)
    finally:
        db.close()

    try:
        card = client.get(
            f"/api/v1/lawyer/clients/{seeded['lead_id']}", headers={"X-API-Key": key}
        ).json()
        assert card["nda"]["nda_id"] == nda_id

        body = client.get(
            f"/api/v1/lawyer/nda/{nda_id}/document", headers={"X-API-Key": key}
        ).json()
        assert body["document_text"] == "Соглашение о конфиденциальности, редакция 3"
        assert body["document_hash"] == "n" * 64
    finally:
        _cleanup(names, seeded["lead_id"])


def test_unknown_document_is_not_found() -> None:
    client = TestClient(app)
    names = ["pytest.workspace.nodoc"]
    key = _key(names[0])
    try:
        missing = "00000000-0000-4000-8000-000000000000"
        assert client.get(f"/api/v1/lawyer/agreements/{missing}/document", headers={"X-API-Key": key}).status_code == 404
        assert client.get(f"/api/v1/lawyer/nda/{missing}/document", headers={"X-API-Key": key}).status_code == 404
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ApiKey).where(ApiKey.name.in_(names)))
            db.commit()
            cache.invalidate()
        finally:
            db.close()


def test_client_list_shows_only_those_with_intakes() -> None:
    """В таблице лидов лежат и те, кто просто нажал кнопку, — в рабочем месте они лишние."""
    client = TestClient(app)
    names = ["pytest.workspace.list"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        db.add(Lead(name="Просто нажал кнопку", contact="@idle", source=LeadSource.telegram_bot))
        db.commit()
    finally:
        db.close()

    try:
        rows = client.get("/api/v1/lawyer/clients", headers={"X-API-Key": key}).json()
        names_shown = [r["name"] for r in rows]
        assert "Рябов Александр" in names_shown
        assert "Просто нажал кнопку" not in names_shown
    finally:
        _cleanup(names, seeded["lead_id"])
        db = SessionLocal()
        try:
            db.execute(delete(Lead).where(Lead.name == "Просто нажал кнопку"))
            db.commit()
        finally:
            db.close()


def test_search_finds_by_name() -> None:
    client = TestClient(app)
    names = ["pytest.workspace.search"]
    key = _key(names[0])
    seeded = _seed()
    try:
        rows = client.get(
            "/api/v1/lawyer/clients?search=рябов", headers={"X-API-Key": key}
        ).json()
        assert any(r["lead_id"] == seeded["lead_id"] for r in rows)
        empty = client.get(
            "/api/v1/lawyer/clients?search=такогонет", headers={"X-API-Key": key}
        ).json()
        assert empty == []
    finally:
        _cleanup(names, seeded["lead_id"])


def test_unknown_client_is_not_found() -> None:
    from uuid import uuid4

    client = TestClient(app)
    names = ["pytest.workspace.404"]
    key = _key(names[0])
    try:
        response = client.get(
            f"/api/v1/lawyer/clients/{uuid4()}", headers={"X-API-Key": key}
        )
        assert response.status_code == 404
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ApiKey).where(ApiKey.name.in_(names)))
            db.commit()
            cache.invalidate()
        finally:
            db.close()
