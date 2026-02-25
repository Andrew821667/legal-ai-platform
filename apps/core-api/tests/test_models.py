from __future__ import annotations

from core_api.models import ContractJobStatus, LeadStatus, ScheduledPostStatus


def test_enum_values() -> None:
    assert LeadStatus.new.value == "new"
    assert ScheduledPostStatus.scheduled.value == "scheduled"
    assert ContractJobStatus.processing.value == "processing"
