"""Хранение состояния уточняющего диалога между перезапусками бота.

У бота нет персистентности python-telegram-bot: user_data живёт в памяти
процесса. Для большинства сценариев это не страшно — человек нажмёт кнопку
заново. Здесь страшно: диалог идёт минутами, деплой может прийтись на его
середину, и тогда клиент отвечает на заданный вопрос, а получает ответ из
общей воронки. Со стороны это выглядит так, будто его перестали слушать.

Поэтому состояние переживает перезапуск. В нём только ход разговора: на каком
шаге остановились и что уже спрошено. Ответы, документы и подпись уходят в
core-api сразу и от этой таблицы не зависят.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Ключи состояния, которые имеет смысл сохранять. Всё остальное в user_data
# принадлежит другим сценариям, и восстанавливать его при перезапуске нельзя:
# ожидание файла или незакрытая форма ожили бы в неподходящий момент.
_PERSISTED_KEYS = (
    "intake_dialog_stage",
    "intake_dialog_intake_id",
    "intake_dialog_lead_id",
    "intake_dialog_area",
    "intake_dialog_answered",
    "intake_dialog_pending_question",
    "intake_dialog_documents",
    "intake_dialog_nda_signed",
)


def save_state(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    user_data: dict,
) -> None:
    """Сохраняет ход диалога. Сбой записи не должен ронять разговор."""
    payload = {key: user_data[key] for key in _PERSISTED_KEYS if key in user_data}
    if not payload.get("intake_dialog_stage"):
        clear_state(get_connection, telegram_user_id=telegram_user_id)
        return

    try:
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO intake_dialog_state (telegram_user_id, state_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (int(telegram_user_id), json.dumps(payload, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as error:
        logger.warning("Не удалось сохранить состояние диалога %s: %s", telegram_user_id, error)


def load_state(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
) -> dict:
    """Возвращает сохранённый ход диалога или пустой словарь."""
    try:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT state_json FROM intake_dialog_state WHERE telegram_user_id = ?",
                (int(telegram_user_id),),
            ).fetchone()
        finally:
            conn.close()
    except Exception as error:
        logger.warning("Не удалось прочитать состояние диалога %s: %s", telegram_user_id, error)
        return {}

    if not row:
        return {}

    try:
        # Значение могло быть записано прежней версией с другим набором
        # ключей — берём только известные, остальное игнорируем.
        stored = json.loads(row[0] if not isinstance(row, sqlite3.Row) else row["state_json"])
    except (ValueError, TypeError) as error:
        logger.warning("Испорченное состояние диалога %s: %s", telegram_user_id, error)
        return {}

    if not isinstance(stored, dict):
        return {}
    return {key: value for key, value in stored.items() if key in _PERSISTED_KEYS}


def clear_state(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
) -> None:
    """Удаляет состояние: диалог завершён или передан юристу."""
    try:
        conn = get_connection()
        try:
            conn.execute(
                "DELETE FROM intake_dialog_state WHERE telegram_user_id = ?",
                (int(telegram_user_id),),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as error:
        logger.warning("Не удалось очистить состояние диалога %s: %s", telegram_user_id, error)
