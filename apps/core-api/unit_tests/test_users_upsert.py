from __future__ import annotations

from types import SimpleNamespace

from core_api.models import User
from core_api.routers.users import upsert_user
from core_api.schemas import UserCreate
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    User.__table__.create(engine)
    return Session(engine)


def test_email_upsert_preserves_consent_when_defaults_are_unset() -> None:
    db = _session()
    identity = SimpleNamespace()
    try:
        created = upsert_user(
            UserCreate(
                email="lead@example.com",
                name="Первый контакт",
                consent_given=True,
                transborder_consent=True,
            ),
            identity,
            db,
            None,
        )
        updated = upsert_user(
            UserCreate(email="LEAD@example.com", name="Повторный контакт"),
            identity,
            db,
            None,
        )

        assert updated.id == created.id
        assert updated.name == "Повторный контакт"
        assert updated.consent_given is True
        assert updated.transborder_consent is True
    finally:
        db.close()


def test_username_match_is_used_when_supplied_email_is_new() -> None:
    db = _session()
    identity = SimpleNamespace()
    try:
        created = upsert_user(
            UserCreate(username="legal_user", consent_given=True),
            identity,
            db,
            None,
        )
        updated = upsert_user(
            UserCreate(username="LEGAL_USER", email="lead@example.com"),
            identity,
            db,
            None,
        )

        assert updated.id == created.id
        assert updated.email == "lead@example.com"
        assert updated.consent_given is True
    finally:
        db.close()
