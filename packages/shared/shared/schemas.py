from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LeadSource(str, Enum):
    telegram_bot = "telegram_bot"
    website_form = "website_form"
    telegram_channel = "telegram_channel"


class LeadStatus(str, Enum):
    new = "new"
    qualified = "qualified"
    booked = "booked"
    proposal = "proposal"
    won = "won"
    lost = "lost"


class LeadCreateBase(BaseModel):
    source: LeadSource
    legacy_lead_id: int | None = None
    telegram_user_id: int | None = None
    name: str | None = None
    contact: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    segment: str | None = None
    status: LeadStatus = LeadStatus.new
    score: int | None = None
    temperature: str | None = None
    service_category: str | None = None
    specific_need: str | None = None
    pain_point: str | None = None
    budget: str | None = None
    urgency: str | None = None
    industry: str | None = None
    conversation_stage: str | None = None
    cta_variant: str | None = None
    cta_shown: bool = False
    lead_magnet_type: str | None = None
    lead_magnet_delivered: bool = False
    notes: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None


class LeadCreate(LeadCreateBase):
    """Backward-compatible alias for shared lead payload."""


class EventCreateBase(BaseModel):
    lead_id: str | None = None
    user_id: str | None = None
    type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class EventCreate(EventCreateBase):
    """Backward-compatible alias for shared event payload."""


class ScheduledPostCreateBase(BaseModel):
    channel_id: str | None = None
    channel_username: str | None = None
    title: str | None = None
    text: str
    media_urls: list[str] | None = None
    source_url: str | None = None
    source_hash: str | None = None
    rubric: str | None = None
    format_type: str | None = None
    cta_type: str | None = None
    publish_at: datetime | str
    status: str = "scheduled"


class ScheduledPostCreate(ScheduledPostCreateBase):
    """Backward-compatible alias for shared scheduled-post payload."""


class ContractJobCreateBase(BaseModel):
    lead_id: str | None = None
    priority: int = 0
    deadline_at: datetime | None = None
    input_mode: str
    document_name: str | None = None
    document_text: str | None = None
    document_url: str | None = None


class ContractJobCreate(ContractJobCreateBase):
    """Backward-compatible alias for shared contract-job payload."""
