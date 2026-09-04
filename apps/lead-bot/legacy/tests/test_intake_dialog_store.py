"""Хранение хода диалога в локальной базе бота.

Проверяется то, ради чего таблица заведена: состояние переживает
переоткрытие соединения, а испорченные или чужие данные не роняют разговор.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

import database_schema
import intake_dialog_store


@pytest.fixture
def connect(tmp_path: Path):
    db_path = tmp_path / "bot.db"

    def _connect() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    database_schema.init_database(_connect, logging.getLogger("test"))
    return _connect


def test_state_survives_reconnect(connect) -> None:
    intake_dialog_store.save_state(
        connect,
        telegram_user_id=42,
        user_data={
            "intake_dialog_stage": "asking",
            "intake_dialog_intake_id": "abc",
            "intake_dialog_answered": ["side"],
            "intake_dialog_documents": 0,
        },
    )

    restored = intake_dialog_store.load_state(connect, telegram_user_id=42)

    assert restored["intake_dialog_stage"] == "asking"
    assert restored["intake_dialog_intake_id"] == "abc"
    assert restored["intake_dialog_answered"] == ["side"]


def test_unknown_user_has_no_state(connect) -> None:
    assert intake_dialog_store.load_state(connect, telegram_user_id=999) == {}


def test_saving_again_replaces_previous_state(connect) -> None:
    for stage in ("asking", "documents"):
        intake_dialog_store.save_state(
            connect,
            telegram_user_id=7,
            user_data={"intake_dialog_stage": stage, "intake_dialog_intake_id": "abc"},
        )

    assert intake_dialog_store.load_state(connect, telegram_user_id=7)["intake_dialog_stage"] == "documents"


def test_finished_dialog_is_removed(connect) -> None:
    """Пустая стадия означает завершение — строка не должна оставаться."""
    intake_dialog_store.save_state(
        connect, telegram_user_id=7, user_data={"intake_dialog_stage": "asking"}
    )
    intake_dialog_store.save_state(connect, telegram_user_id=7, user_data={})

    assert intake_dialog_store.load_state(connect, telegram_user_id=7) == {}


def test_foreign_keys_are_not_restored(connect) -> None:
    """Восстанавливаем только ход диалога.

    Остальное в user_data принадлежит другим сценариям: ожидание файла или
    незакрытая форма ожили бы после перезапуска в неподходящий момент.
    """
    intake_dialog_store.save_state(
        connect,
        telegram_user_id=5,
        user_data={
            "intake_dialog_stage": "asking",
            "contract_analysis_waiting": True,
            "какой-то_чужой_ключ": "значение",
        },
    )

    restored = intake_dialog_store.load_state(connect, telegram_user_id=5)

    assert restored == {"intake_dialog_stage": "asking"}


def test_corrupted_state_does_not_raise(connect) -> None:
    """Испорченная строка не должна ронять разговор — начнём с чистого листа."""
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO intake_dialog_state (telegram_user_id, state_json) VALUES (?, ?)",
            (11, "{это не json"),
        )
        conn.commit()
    finally:
        conn.close()

    assert intake_dialog_store.load_state(connect, telegram_user_id=11) == {}


def test_clearing_is_idempotent(connect) -> None:
    intake_dialog_store.clear_state(connect, telegram_user_id=404)
    intake_dialog_store.clear_state(connect, telegram_user_id=404)


def test_database_failure_does_not_raise(tmp_path: Path) -> None:
    """Недоступная база не должна прерывать разговор с клиентом."""

    def _broken() -> sqlite3.Connection:
        raise sqlite3.OperationalError("база недоступна")

    intake_dialog_store.save_state(
        _broken, telegram_user_id=1, user_data={"intake_dialog_stage": "asking"}
    )
    assert intake_dialog_store.load_state(_broken, telegram_user_id=1) == {}
    intake_dialog_store.clear_state(_broken, telegram_user_id=1)
