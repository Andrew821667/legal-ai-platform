"""Объединение учётной записи сайта (Яндекс ID) с Telegram по согласию клиента.

Закрепляется: код из бота, введённый на сайте, не объединяет сразу — бот
показывает владельцу Telegram почту учётной записи и объединяет только после
«Да»; «Нет, это не я» — отказ; две свежие сессии объединяют сразу, но в Telegram
приходит уведомление с «Отвязать»; код одноразовый и истекает; чужой Telegram не
перехватывается; дела видны в обе стороны; подпись после входа через Яндекс ID
остаётся подписью через Яндекс ID; отвязка возвращает как было.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import json

import pytest
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import AuditLog, ClientAccount, ClientLinkCode, Lead, Scope, ServiceAgreement
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from test_client_accounts import _login, world  # noqa: F401 — фикстура
from test_client_archive import _cleanup, _key


@pytest.fixture
def telegram(monkeypatch) -> list[dict]:
    """Сообщения, которые ядро отправило бы в Telegram."""
    sent: list[dict] = []

    def _send(token, chat_id, text, reply_markup=None, parse_mode=None):
        sent.append({"chat_id": int(chat_id), "text": text, "markup": json.loads(reply_markup) if reply_markup else None})
        return {"message_id": len(sent)}

    import core_api.routers.client_auth as router
    import core_api.telegram_delivery as delivery

    monkeypatch.setattr(router, "_post_telegram_message", _send)
    monkeypatch.setattr(delivery, "_client_token", lambda: "token")
    return sent


def _buttons(message: dict) -> list[str]:
    return [button["callback_data"] for row in message["markup"]["inline_keyboard"] for button in row]


def _decide(client, bot, message: dict, telegram_user_id: int, *, accept: bool = True):
    data = next(b for b in _buttons(message) if b.startswith("clink:ok:" if accept else "clink:no:"))
    code_id = data.rsplit(":", 1)[1]
    return client.post(f"/api/v1/client-auth/telegram-link-codes/{code_id}/decision",
                       json={"telegram_user_id": telegram_user_id, "accept": accept}, headers=bot)


@pytest.fixture
def linked_world(world, telegram):  # noqa: F811
    db = SessionLocal()
    try:
        telegram_user_id = db.get(Lead, world["ids"]["telegram"]).telegram_user_id
    finally:
        db.close()
    extra_email = f"other-{uuid4().hex[:8]}@yandex.ru"
    yield {**world, "tg": telegram_user_id, "extra_email": extra_email, "sent": telegram}
    db = SessionLocal()
    try:
        db.execute(delete(ClientLinkCode).where(ClientLinkCode.telegram_user_id.in_([telegram_user_id, telegram_user_id + 1])))
        db.execute(delete(ClientAccount).where(ClientAccount.email == extra_email))
        db.commit()
    finally:
        db.close()


def _code(client, bot, telegram_user_id, username="anna_tg"):
    response = client.post("/api/v1/client-auth/telegram-link-codes",
                           json={"telegram_user_id": telegram_user_id, "telegram_username": username}, headers=bot)
    assert response.status_code == 200, response.text
    return response.json()


def _link(client, bot, account_id, **body):
    return client.post(f"/api/v1/client-auth/accounts/{account_id}/telegram", json=body, headers=bot)


def _summary(client, bot, **query):
    key, value = next(iter(query.items()))
    return client.get(f"/api/v1/client-portal/summary?{key}={value}", headers=bot).json()


def test_bot_code_links_telegram_and_cases_are_seen_both_ways(linked_world) -> None:
    w = linked_world
    client = TestClient(app)
    account_id = _login(client, w["bot"], w["email"]).json()["client_account_id"]
    before = {a["id"] for a in _summary(client, w["bot"], client_account_id=account_id)["agreements"]}
    assert w["ids"]["foreign"] not in before

    issued = _code(client, w["bot"], w["tg"])
    assert issued["linked"] is False
    assert len(issued["code"]) == 9 and issued["code"][4] == "-"
    # Клиент вводит как удобно: строчными, без дефиса, с пробелами.
    typed = f" {issued['code'].replace('-', '').lower()} "
    pending = _link(client, w["bot"], account_id, code=typed)
    assert pending.status_code == 200, pending.text
    # Код не объединяет сразу: бот спрашивает владельца Telegram, показав почту.
    assert pending.json()["pending"] is True and pending.json()["telegram_user_id"] is None
    account = client.get(f"/api/v1/client-auth/accounts/{account_id}", headers=w["bot"]).json()
    assert account["link_pending"] is True
    [question] = w["sent"]
    assert question["chat_id"] == w["tg"]
    assert w["email"] in question["text"] and "Объединить" in question["text"]
    assert any(b.startswith("clink:no:") for b in _buttons(question))
    assert _summary(client, w["bot"], client_account_id=account_id)["client"]["telegram_linked"] is False

    # Нажать за владельца чужим Telegram нельзя.
    assert _decide(client, w["bot"], question, w["tg"] + 1).status_code == 410
    decided = _decide(client, w["bot"], question, w["tg"])
    assert decided.status_code == 200, decided.text
    assert decided.json() == {"status": "linked", "email": w["email"]}
    linked = client.get(f"/api/v1/client-auth/accounts/{account_id}", headers=w["bot"]).json()
    assert linked["telegram_user_id"] == w["tg"]
    assert linked["telegram_username"] == "anna_tg"
    assert linked["telegram_linked_at"] and linked["link_pending"] is False
    # Повторное нажатие — запрос уже закрыт.
    assert _decide(client, w["bot"], question, w["tg"]).status_code == 410

    via_site = {a["id"] for a in _summary(client, w["bot"], client_account_id=account_id)["agreements"]}
    assert {w["ids"]["own"], w["ids"]["foreign"]} <= via_site
    via_telegram = _summary(client, w["bot"], telegram_user_id=w["tg"])
    assert w["ids"]["own"] in {a["id"] for a in via_telegram["agreements"]}
    assert via_telegram["client"]["via"] == "telegram"

    # Код одноразовый.
    assert _link(client, w["bot"], account_id, code=issued["code"]).status_code == 400
    # Бот больше кода не выдаёт — говорит, к какой почте привязан.
    again = _code(client, w["bot"], w["tg"])
    assert again == {"linked": True, "email_masked": f"{w['email'][0]}***@yandex.ru"}

    db = SessionLocal()
    try:
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "client_account.telegram_linked",
                                                 AuditLog.target_id == UUID(account_id)))
        assert audit is not None and audit.details == {"method": "bot_code"}
    finally:
        db.close()


def test_owner_says_it_was_not_me(linked_world) -> None:
    w = linked_world
    client = TestClient(app)
    account_id = _login(client, w["bot"], w["email"]).json()["client_account_id"]
    issued = _code(client, w["bot"], w["tg"])
    assert _link(client, w["bot"], account_id, code=issued["code"]).json()["pending"] is True
    declined = _decide(client, w["bot"], w["sent"][0], w["tg"], accept=False)
    assert declined.json()["status"] == "declined"
    account = client.get(f"/api/v1/client-auth/accounts/{account_id}", headers=w["bot"]).json()
    assert account["telegram_user_id"] is None and account["link_pending"] is False
    # Код сгорел вместе с отказом.
    assert _link(client, w["bot"], account_id, code=issued["code"]).status_code == 400


def test_code_is_kept_when_telegram_is_unreachable(linked_world, monkeypatch) -> None:
    w = linked_world
    client = TestClient(app)
    account_id = _login(client, w["bot"], w["email"]).json()["client_account_id"]
    issued = _code(client, w["bot"], w["tg"])

    import core_api.routers.client_auth as router

    def _down(*args, **kwargs):
        raise TimeoutError("telegram is down")

    monkeypatch.setattr(router, "_post_telegram_message", _down)
    failed = _link(client, w["bot"], account_id, code=issued["code"])
    assert failed.status_code == 502 and failed.json()["detail"] == "telegram_unavailable"
    assert client.get(f"/api/v1/client-auth/accounts/{account_id}", headers=w["bot"]).json()["link_pending"] is False


def test_wrong_expired_and_replaced_codes_are_refused(linked_world) -> None:
    w = linked_world
    client = TestClient(app)
    account_id = _login(client, w["bot"], w["email"]).json()["client_account_id"]
    assert _link(client, w["bot"], account_id, code="ABCD-EFGH").json()["detail"] == "invalid_code"
    assert _link(client, w["bot"], account_id, code="short").status_code == 400

    first = _code(client, w["bot"], w["tg"])
    second = _code(client, w["bot"], w["tg"])
    # Новый код гасит прежний.
    assert _link(client, w["bot"], account_id, code=first["code"]).status_code == 400

    db = SessionLocal()
    try:
        db.execute(update(ClientLinkCode).where(ClientLinkCode.telegram_user_id == w["tg"])
                   .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        db.commit()
    finally:
        db.close()
    assert _link(client, w["bot"], account_id, code=second["code"]).status_code == 400
    assert _summary(client, w["bot"], client_account_id=account_id)["client"]["telegram_linked"] is False


def test_telegram_is_not_taken_from_another_account(linked_world) -> None:
    w = linked_world
    client = TestClient(app)
    account_id = _login(client, w["bot"], w["email"]).json()["client_account_id"]
    other_id = _login(client, w["bot"], w["extra_email"], yandex_id=f"ya-{uuid4().hex[:6]}").json()["client_account_id"]

    assert _link(client, w["bot"], account_id, telegram_user_id=w["tg"]).status_code == 200
    # По двум сессиям — сразу, но владелец Telegram узнаёт и может отвязать.
    [notice] = w["sent"]
    assert notice["chat_id"] == w["tg"] and w["email"] in notice["text"]
    assert _buttons(notice) == [f"clink:undo:{account_id}"]
    # Тот же Telegram к другой учётной записи — отказ, и по коду тоже нельзя:
    # бот не выдаёт код уже привязанному Telegram.
    taken = _link(client, w["bot"], other_id, telegram_user_id=w["tg"])
    assert taken.status_code == 409 and taken.json()["detail"] == "telegram_linked_elsewhere"
    # Другой Telegram к уже привязанной записи — сначала отвязать.
    other_tg = _link(client, w["bot"], account_id, telegram_user_id=w["tg"] + 1)
    assert other_tg.status_code == 409 and other_tg.json()["detail"] == "account_has_other_telegram"
    # Повтор той же пары — не ошибка.
    assert _link(client, w["bot"], account_id, telegram_user_id=w["tg"]).status_code == 200
    # Код или Telegram — ровно одно.
    assert _link(client, w["bot"], account_id).status_code == 422
    assert _link(client, w["bot"], account_id, code="ABCD-EFGH", telegram_user_id=w["tg"]).status_code == 422


def test_signature_after_yandex_login_stays_yandex_when_telegram_is_linked(linked_world) -> None:
    """Способ подписи — способ входа: Telegram привязан, но вошёл через Яндекс ID."""
    w = linked_world
    client = TestClient(app)
    account_id = _login(client, w["bot"], w["email"]).json()["client_account_id"]
    assert _link(client, w["bot"], account_id, telegram_user_id=w["tg"]).status_code == 200

    def sign(agreement_id: str):
        return client.post(f"/api/v1/service-agreements/{agreement_id}/sign",
                           json={"client_account_id": account_id, "document_hash": w["ids"]["own_hash"],
                                 "callback_id": f"lnk-{agreement_id[:8]}", "channel": "miniapp"},
                           headers=w["bot"])

    # Прежняя редакция называет только Telegram — после Яндекс ID нельзя и с привязкой.
    assert sign(w["ids"]["own"]).status_code == 409
    fresh = sign(w["ids"]["fresh"])
    assert fresh.status_code == 201, fresh.text
    db = SessionLocal()
    try:
        from core_api.routers.service_agreements import _certificate_rows

        row = db.get(ServiceAgreement, w["ids"]["fresh"])
        assert row.signer_telegram_user_id is None
        assert str(row.signer_account_id) == account_id
        assert row.signer_email == w["email"]
        assert dict(_certificate_rows(db, row))["Способ подписания"] == "личный кабинет, вход через Яндекс ID"
    finally:
        db.close()


def test_unlink_returns_the_account_to_site_cases_only(linked_world) -> None:
    w = linked_world
    client = TestClient(app)
    account_id = _login(client, w["bot"], w["email"]).json()["client_account_id"]
    assert _link(client, w["bot"], account_id, telegram_user_id=w["tg"], telegram_username="@anna").status_code == 200
    assert _summary(client, w["bot"], client_account_id=account_id)["client"]["telegram_linked"] is True

    unlinked = client.delete(f"/api/v1/client-auth/accounts/{account_id}/telegram", headers=w["bot"])
    assert unlinked.status_code == 200
    assert unlinked.json()["telegram_user_id"] is None and unlinked.json()["telegram_username"] is None
    after = _summary(client, w["bot"], client_account_id=account_id)
    assert w["ids"]["foreign"] not in {a["id"] for a in after["agreements"]}
    assert w["ids"]["own"] not in {a["id"] for a in _summary(client, w["bot"], telegram_user_id=w["tg"])["agreements"]}
    # «Отвязать» из бота — только владельцу этого Telegram.
    assert _link(client, w["bot"], account_id, telegram_user_id=w["tg"]).status_code == 200
    owner_unlink = f"/api/v1/client-auth/accounts/{account_id}/telegram/owner-unlink"
    assert client.post(owner_unlink, json={"telegram_user_id": w["tg"] + 1}, headers=w["bot"]).status_code == 403
    assert client.post(owner_unlink, json={"telegram_user_id": w["tg"]}, headers=w["bot"]).json()["status"] == "unlinked"
    # Повторная отвязка — не ошибка; неизвестная запись — 404.
    assert client.delete(f"/api/v1/client-auth/accounts/{account_id}/telegram", headers=w["bot"]).status_code == 200
    assert client.delete(f"/api/v1/client-auth/accounts/{uuid4()}/telegram", headers=w["bot"]).status_code == 404


def test_link_endpoints_need_the_bot_key(linked_world) -> None:
    w = linked_world
    client = TestClient(app)
    name = f"pytest.link.{uuid4().hex}"
    news = {"X-API-Key": _key(Scope.news, name)}
    try:
        account_id = _login(client, w["bot"], w["email"]).json()["client_account_id"]
        body = {"telegram_user_id": w["tg"]}
        assert client.post("/api/v1/client-auth/telegram-link-codes", json=body).status_code == 401
        assert client.post("/api/v1/client-auth/telegram-link-codes", json=body, headers=news).status_code == 403
        assert client.post(f"/api/v1/client-auth/accounts/{account_id}/telegram", json=body, headers=news).status_code == 403
        assert client.delete(f"/api/v1/client-auth/accounts/{account_id}/telegram", headers=news).status_code == 403
    finally:
        _cleanup([name], [])
