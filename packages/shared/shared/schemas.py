from __future__ import annotations

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


class LeadCreate(BaseModel):
    source: LeadSource
    telegram_user_id: int | None = None
    name: str | None = None
    contact: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None


class EventCreate(BaseModel):
    lead_id: str | None = None
    user_id: str | None = None
    type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class ScheduledPostCreate(BaseModel):
    text: str
    publish_at: str
    status: str = "scheduled"


class ContractJobCreate(BaseModel):
    input_mode: str
    document_text: str | None = None
    document_url: str | None = None
