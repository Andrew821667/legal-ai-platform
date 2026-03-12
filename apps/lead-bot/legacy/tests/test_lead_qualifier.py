from __future__ import annotations

import os
import tempfile

from database import Database
from lead_qualifier import LeadQualifier


def test_process_lead_data_skips_new_lead_without_contact() -> None:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        db = Database(db_path)
        qualifier = LeadQualifier(db)
        user_id = db.create_or_update_user(
            telegram_id=555001,
            username="no_contact",
            first_name="NoContact",
        )

        lead_id = qualifier.process_lead_data(
            user_id,
            {
                "pain_point": "Ничего не понял",
                "lead_temperature": "cold",
                "service_category": "legal_ops",
            },
        )

        assert lead_id is None
        assert db.get_lead_by_user_id(user_id) is None
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_process_lead_data_updates_existing_contacted_lead_without_new_contact() -> None:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        db = Database(db_path)
        qualifier = LeadQualifier(db)
        user_id = db.create_or_update_user(
            telegram_id=555002,
            username="existing_contact",
            first_name="Existing",
        )
        existing_lead_id = db.create_or_update_lead(
            user_id,
            {
                "name": "Existing",
                "phone": "+79092330909",
                "temperature": "warm",
            },
        )

        lead_id = qualifier.process_lead_data(
            user_id,
            {
                "pain_point": "Теряются юридические запросы",
                "lead_temperature": "warm",
                "service_category": "legal_ops",
            },
        )

        lead = db.get_lead_by_user_id(user_id)
        assert lead_id == existing_lead_id
        assert lead is not None
        assert lead["phone"] == "+79092330909"
        assert lead["pain_point"] == "Теряются юридические запросы"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
