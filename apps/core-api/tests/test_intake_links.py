"""Связь между обращениями двух разных клиентов по одному фактическому делу.

Найдено вживую: один клиент упоминал бывшего супруга другого клиента как
противоположную сторону в том же имущественном споре, а проверка конфликта
у каждого обращения шла независимо — юрист узнавал о связи только по памяти.
"""

from __future__ import annotations

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, Lead, LeadSource, LegalIntake, LegalIntakeStatus, Scope
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


def _client_with_intake(name: str, contact: str) -> dict:
    db = SessionLocal()
    try:
        lead = Lead(name=name, contact=contact, source=LeadSource.telegram_bot)
        db.add(lead)
        db.flush()
        intake = LegalIntake(
            lead_id=lead.id,
            description="Раздел совместно нажитого имущества.",
            status=LegalIntakeStatus.received,
        )
        db.add(intake)
        db.commit()
        return {"lead_id": str(lead.id), "intake_id": str(intake.id)}
    finally:
        db.close()


def _cleanup(keys: list[str], lead_ids: list[str]) -> None:
    db = SessionLocal()
    try:
        for lead_id in lead_ids:
            db.execute(delete(LegalIntake).where(LegalIntake.lead_id == lead_id))
            db.execute(delete(Lead).where(Lead.id == lead_id))
        db.execute(delete(ApiKey).where(ApiKey.name.in_(keys)))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def _links_of(card: dict) -> list[dict]:
    (intake,) = card["intakes"]
    return intake["links"]


def test_subordinate_link_shows_main_and_secondary_on_each_card() -> None:
    """«Дело другого клиента основное» — секретарь читает это с любой карточки."""
    client = TestClient(app)
    names = ["pytest.links.subordinate"]
    key = _key(names[0])
    main_client = _client_with_intake("Рябов Александр", "@ryabov_main")
    secondary_client = _client_with_intake("Рябова Алёна", "@ryabova_secondary")
    try:
        response = client.post(
            f"/api/v1/lawyer/intakes/{secondary_client['intake_id']}/links",
            json={"linked_lead_id": main_client["lead_id"], "role": "subordinate"},
            headers={"X-API-Key": key},
        )
        assert response.status_code == 200, response.text
        link_id = response.json()["link_id"]

        secondary_card = client.get(
            f"/api/v1/lawyer/clients/{secondary_client['lead_id']}", headers={"X-API-Key": key}
        ).json()
        (link,) = _links_of(secondary_card)
        assert link["role"] == "subordinate"
        assert link["linked_lead_id"] == main_client["lead_id"]
        assert link["linked_client"] == "Рябов Александр"
        assert link["link_id"] == link_id

        main_card = client.get(
            f"/api/v1/lawyer/clients/{main_client['lead_id']}", headers={"X-API-Key": key}
        ).json()
        (reverse_link,) = _links_of(main_card)
        assert reverse_link["role"] == "main"
        assert reverse_link["linked_lead_id"] == secondary_client["lead_id"]
        assert reverse_link["linked_client"] == "Рябова Алёна"
        assert reverse_link["link_id"] == link_id
    finally:
        _cleanup(names, [main_client["lead_id"], secondary_client["lead_id"]])


def test_main_link_from_the_main_side_produces_the_same_pair() -> None:
    """Связь можно завести и с главной стороны — «это дело основное»."""
    client = TestClient(app)
    names = ["pytest.links.main_side"]
    key = _key(names[0])
    main_client = _client_with_intake("Главный", "@main_side")
    secondary_client = _client_with_intake("Второстепенный", "@secondary_side")
    try:
        response = client.post(
            f"/api/v1/lawyer/intakes/{main_client['intake_id']}/links",
            json={"linked_lead_id": secondary_client["lead_id"], "role": "main"},
            headers={"X-API-Key": key},
        )
        assert response.status_code == 200, response.text

        main_card = client.get(
            f"/api/v1/lawyer/clients/{main_client['lead_id']}", headers={"X-API-Key": key}
        ).json()
        secondary_card = client.get(
            f"/api/v1/lawyer/clients/{secondary_client['lead_id']}", headers={"X-API-Key": key}
        ).json()
        assert _links_of(main_card)[0]["role"] == "main"
        assert _links_of(secondary_card)[0]["role"] == "subordinate"
    finally:
        _cleanup(names, [main_client["lead_id"], secondary_client["lead_id"]])


def test_joint_link_has_no_hierarchy() -> None:
    """Общее рассмотрение — обе стороны видят одну и ту же роль."""
    client = TestClient(app)
    names = ["pytest.links.joint"]
    key = _key(names[0])
    a = _client_with_intake("Клиент А", "@client_a")
    b = _client_with_intake("Клиент Б", "@client_b")
    try:
        response = client.post(
            f"/api/v1/lawyer/intakes/{a['intake_id']}/links",
            json={"linked_lead_id": b["lead_id"], "role": "joint", "note": "один договор поставки"},
            headers={"X-API-Key": key},
        )
        assert response.status_code == 200, response.text

        card_a = client.get(f"/api/v1/lawyer/clients/{a['lead_id']}", headers={"X-API-Key": key}).json()
        card_b = client.get(f"/api/v1/lawyer/clients/{b['lead_id']}", headers={"X-API-Key": key}).json()
        assert _links_of(card_a)[0]["role"] == "joint"
        assert _links_of(card_b)[0]["role"] == "joint"
        assert _links_of(card_a)[0]["note"] == "один договор поставки"
    finally:
        _cleanup(names, [a["lead_id"], b["lead_id"]])


def test_cannot_link_intake_to_itself() -> None:
    client = TestClient(app)
    names = ["pytest.links.self"]
    key = _key(names[0])
    a = _client_with_intake("Одинокий клиент", "@lonely")
    try:
        response = client.post(
            f"/api/v1/lawyer/intakes/{a['intake_id']}/links",
            json={"linked_lead_id": a["lead_id"], "role": "joint"},
            headers={"X-API-Key": key},
        )
        assert response.status_code == 400
    finally:
        _cleanup(names, [a["lead_id"]])


def test_linking_to_a_lead_without_an_intake_is_not_found() -> None:
    """В таблице лидов есть и те, кто просто нажал кнопку в боте, — с ними связывать нечего."""
    client = TestClient(app)
    names = ["pytest.links.no_intake"]
    key = _key(names[0])
    a = _client_with_intake("С обращением", "@has_intake")
    db = SessionLocal()
    try:
        idle_lead = Lead(name="Без обращения", contact="@idle", source=LeadSource.telegram_bot)
        db.add(idle_lead)
        db.commit()
        idle_lead_id = str(idle_lead.id)
    finally:
        db.close()
    try:
        response = client.post(
            f"/api/v1/lawyer/intakes/{a['intake_id']}/links",
            json={"linked_lead_id": idle_lead_id, "role": "joint"},
            headers={"X-API-Key": key},
        )
        assert response.status_code == 404
    finally:
        _cleanup(names, [a["lead_id"], idle_lead_id])


def test_duplicate_link_in_either_direction_is_rejected() -> None:
    """Повторная связь той же пары — не новая строка, а понятная ошибка."""
    client = TestClient(app)
    names = ["pytest.links.duplicate"]
    key = _key(names[0])
    a = _client_with_intake("Первый", "@first")
    b = _client_with_intake("Второй", "@second")
    try:
        first = client.post(
            f"/api/v1/lawyer/intakes/{a['intake_id']}/links",
            json={"linked_lead_id": b["lead_id"], "role": "joint"},
            headers={"X-API-Key": key},
        )
        assert first.status_code == 200

        same_direction = client.post(
            f"/api/v1/lawyer/intakes/{a['intake_id']}/links",
            json={"linked_lead_id": b["lead_id"], "role": "subordinate"},
            headers={"X-API-Key": key},
        )
        assert same_direction.status_code == 409

        reverse_direction = client.post(
            f"/api/v1/lawyer/intakes/{b['intake_id']}/links",
            json={"linked_lead_id": a["lead_id"], "role": "subordinate"},
            headers={"X-API-Key": key},
        )
        assert reverse_direction.status_code == 409
    finally:
        _cleanup(names, [a["lead_id"], b["lead_id"]])


def test_unknown_link_type_is_rejected() -> None:
    client = TestClient(app)
    names = ["pytest.links.bad_type"]
    key = _key(names[0])
    a = _client_with_intake("А", "@a_bad_type")
    b = _client_with_intake("Б", "@b_bad_type")
    try:
        response = client.post(
            f"/api/v1/lawyer/intakes/{a['intake_id']}/links",
            json={"linked_lead_id": b["lead_id"], "role": "merged"},
            headers={"X-API-Key": key},
        )
        assert response.status_code == 400
    finally:
        _cleanup(names, [a["lead_id"], b["lead_id"]])


def test_deleting_a_link_removes_it_from_both_cards() -> None:
    client = TestClient(app)
    names = ["pytest.links.delete"]
    key = _key(names[0])
    a = _client_with_intake("Удаляемый А", "@del_a")
    b = _client_with_intake("Удаляемый Б", "@del_b")
    try:
        created = client.post(
            f"/api/v1/lawyer/intakes/{a['intake_id']}/links",
            json={"linked_lead_id": b["lead_id"], "role": "joint"},
            headers={"X-API-Key": key},
        ).json()

        response = client.delete(
            f"/api/v1/lawyer/intakes/links/{created['link_id']}", headers={"X-API-Key": key}
        )
        assert response.status_code == 200

        card_a = client.get(f"/api/v1/lawyer/clients/{a['lead_id']}", headers={"X-API-Key": key}).json()
        card_b = client.get(f"/api/v1/lawyer/clients/{b['lead_id']}", headers={"X-API-Key": key}).json()
        assert _links_of(card_a) == []
        assert _links_of(card_b) == []
    finally:
        _cleanup(names, [a["lead_id"], b["lead_id"]])


def test_deleting_an_unknown_link_is_not_found() -> None:
    client = TestClient(app)
    names = ["pytest.links.delete_missing"]
    key = _key(names[0])
    try:
        response = client.delete(
            "/api/v1/lawyer/intakes/links/11111111-1111-4111-8111-111111111111",
            headers={"X-API-Key": key},
        )
        assert response.status_code == 404
    finally:
        _cleanup(names, [])
