"""Отзыв согласия: ядро обезличивает обращения, бот удаляет свою переписку,
а ответ человеку говорит ровно то, что сделано (ч. 5 ст. 21 152-ФЗ)."""
from __future__ import annotations

import admin_interface
import content


def test_core_result_is_combined_with_local_history_deletion(monkeypatch) -> None:
    iface = admin_interface.admin_interface
    calls: list[int] = []
    monkeypatch.setattr(
        iface, "_core_request_json",
        lambda method, path, **kwargs: {"telegram_user_id": 5, "users_updated": 1, "leads_anonymized": 2, "leads_kept": 1, "messages_deleted": 0},
    )
    monkeypatch.setattr(iface.db, "get_user_by_telegram_id", lambda tg: {"id": 77})

    def _local(user_id):
        calls.append(user_id)
        return {"users_updated": 1, "leads_anonymized": 0, "messages_deleted": 14}

    monkeypatch.setattr(iface.db, "revoke_user_consent_and_delete_data", _local)

    result = iface.clear_user_data_by_telegram_id(5)

    # Раньше при работающем ядре локальная переписка оставалась.
    assert calls == [77]
    assert (result["leads_anonymized"], result["leads_kept"], result["messages_deleted"]) == (2, 1, 14)


def test_reply_names_what_was_done_and_what_is_kept() -> None:
    text = content.consent_revoked_details_text({"leads_anonymized": 2, "leads_kept": 1, "messages_deleted": 14})
    assert "Обработка ваших данных прекращена" in text
    assert "Обращения обезличены: 2" in text
    assert "Удалено сообщений нашей переписки в боте: 14" in text
    assert "По договору сохранено обращений: 1" in text
    assert "история диалога удалена" not in text


def test_reply_without_contract_does_not_mention_kept_cases() -> None:
    text = content.consent_revoked_details_text({"leads_anonymized": 1, "leads_kept": 0, "messages_deleted": 3})
    assert "По договору" not in text
