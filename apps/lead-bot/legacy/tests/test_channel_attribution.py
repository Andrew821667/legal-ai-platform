"""Заявка человека, пришедшего по кнопке под постом канала, помечена «из канала»."""

from __future__ import annotations

from lead_qualifier import LeadQualifier


class _Db:
    def __init__(self, event: dict | None, existing: dict | None = None) -> None:
        self.event = event
        self.existing = existing
        self.saved: dict | None = None

    def get_lead_by_user_id(self, user_id):
        return self.existing

    def last_event_payload(self, user_id, event_type, within_days=30):
        assert event_type == "channel_post_start"
        return self.event

    def create_or_update_lead(self, user_id, lead_data):
        self.saved = dict(lead_data)
        return 5


def test_new_lead_after_channel_post_is_marked_as_channel() -> None:
    db = _Db({"post_id": "p-1", "post_title": "Суд и ИИ"})
    assert LeadQualifier(db).process_lead_data(1, {"name": "Анна", "phone": "+79001234567"}) == 5
    assert db.saved["cta_variant"] == "channel_post"
    assert db.saved["notes"] == "[CHANNEL_POST] post_id=p-1 title=Суд и ИИ"


def test_without_channel_visit_or_for_existing_lead_nothing_is_added() -> None:
    db = _Db(None)
    LeadQualifier(db).process_lead_data(1, {"name": "Анна", "phone": "+79001234567"})
    assert "cta_variant" not in db.saved

    existing = _Db({"post_id": "p-1"}, existing={"id": 3, "phone": "+79001234567"})
    LeadQualifier(existing).process_lead_data(1, {"pain_point": "Нужен бот для заявок"})
    assert "cta_variant" not in existing.saved
