"""Свежесть бэкапа: о пропавшем или неудачном бэкапе владелец узнаёт один раз.

Закрепляется: не настроен — молчим; дампа нет больше суток или копия на NAS
не удалась — одно сообщение; повтор такта не дублирует; удачный бэкап
сбрасывает отметку.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from core_api import backup_health
from core_api.db import SessionLocal
from core_api.models import ClientNotice, ServiceHealth
from sqlalchemy import delete, select

NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def clean():
    def wipe():
        db = SessionLocal()
        try:
            db.execute(delete(ServiceHealth).where(ServiceHealth.key == backup_health.KEY))
            db.execute(delete(ClientNotice).where(ClientNotice.event_key.like("backup:%")))
            db.commit()
        finally:
            db.close()

    wipe()
    yield
    wipe()


def _row(**values) -> None:
    db = SessionLocal()
    try:
        row = db.get(ServiceHealth, backup_health.KEY) or ServiceHealth(key=backup_health.KEY)
        for key, value in values.items():
            setattr(row, key, value)
        db.add(row)
        db.commit()
    finally:
        db.close()


def _notices() -> list[str]:
    db = SessionLocal()
    try:
        return list(db.scalars(select(ClientNotice.text).where(ClientNotice.event_key.like("backup:%"))))
    finally:
        db.close()


def test_not_configured_is_silent() -> None:
    assert backup_health.check(NOW) == {"skipped": "not_configured"}
    assert _notices() == []


def test_fresh_backup_is_fine() -> None:
    _row(ok=True, checked_at=NOW - timedelta(hours=5))
    assert backup_health.check(NOW)["ok"] is True
    assert _notices() == []


def test_stale_backup_alerts_once_and_resets_after_success() -> None:
    _row(ok=True, checked_at=NOW - timedelta(hours=30))
    assert backup_health.check(NOW)["ok"] is False
    backup_health.check(NOW + timedelta(minutes=2))
    [text] = _notices()
    assert "больше суток" in text

    # Ночной скрипт записал удачный бэкап и сбросил отметку.
    _row(ok=True, checked_at=NOW, alerted_at=None)
    assert backup_health.check(NOW)["ok"] is True
    assert len(_notices()) == 1


def test_failed_nas_copy_alerts() -> None:
    _row(ok=False, checked_at=NOW - timedelta(hours=1), last_error="копия на NAS не удалась: NAS 192.168.0.83 недоступен")
    backup_health.check(NOW)
    [text] = _notices()
    assert "NAS" in text


def test_digest_line() -> None:
    db = SessionLocal()
    try:
        assert backup_health.digest_line(db, NOW) is None
    finally:
        db.close()
    _row(ok=True, checked_at=NOW - timedelta(hours=3))
    db = SessionLocal()
    try:
        assert backup_health.digest_line(db, NOW).startswith("Бэкап базы: последний")
    finally:
        db.close()
