from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from core_api.models import (
    ContractJobStatus,
    InputMode,
    LeadSegment,
    LeadSource,
    LeadStatus,
    ScheduledPostStatus,
    Scope,
)


class MessageResponse(BaseModel):
    message: str


class LeadCreate(BaseModel):
    source: LeadSource
    telegram_user_id: int | None = None
    name: str | None = None
    contact: str | None = None
    segment: LeadSegment | None = None
    status: LeadStatus = LeadStatus.new
    score: int | None = None
    notes: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None


class LeadPatch(BaseModel):
    segment: LeadSegment | None = None
    status: LeadStatus | None = None
    score: int | None = None
    notes: str | None = None


class LeadOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    source: LeadSource
    telegram_user_id: int | None
    name: str | None
    contact: str | None
    segment: LeadSegment | None
    status: LeadStatus
    score: int | None
    notes: str | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    utm_content: str | None
    utm_term: str | None

    model_config = {"from_attributes": True}


class EventCreate(BaseModel):
    lead_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class EventOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    lead_id: uuid.UUID | None
    user_id: uuid.UUID | None
    type: str
    payload: dict[str, Any]

    model_config = {"from_attributes": True}


class ScheduledPostCreate(BaseModel):
    channel_id: str | None = None
    channel_username: str | None = None
    title: str | None = None
    text: str
    media_urls: list[str] | None = None
    source_url: str | None = None
    source_hash: str | None = None
    rubric: str | None = None
    publish_at: datetime
    status: ScheduledPostStatus = ScheduledPostStatus.scheduled


class ScheduledPostPatch(BaseModel):
    status: ScheduledPostStatus
    last_error: str | None = None


class ScheduledPostOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    channel_id: str | None
    channel_username: str | None
    title: str | None
    text: str
    media_urls: list[str] | None
    source_url: str | None
    source_hash: str | None
    rubric: str | None
    publish_at: datetime
    status: ScheduledPostStatus
    attempts: int
    max_attempts: int
    last_error: str | None

    model_config = {"from_attributes": True}


class ContractJobCreate(BaseModel):
    lead_id: uuid.UUID | None = None
    priority: int = 0
    deadline_at: datetime | None = None
    input_mode: InputMode
    document_name: str | None = None
    document_text: str | None = None
    document_url: str | None = None


class ContractJobPatch(BaseModel):
    status: ContractJobStatus
    worker_id: str | None = None
    last_error: str | None = None


class ContractJobResult(BaseModel):
    result_summary: str | None = None
    result_json: dict[str, Any] | None = None
    report_url: str | None = None


class ContractJobOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    lead_id: uuid.UUID | None
    worker_id: str | None
    status: ContractJobStatus
    priority: int
    deadline_at: datetime | None
    input_mode: InputMode
    document_name: str | None
    document_text: str | None
    document_url: str | None
    result_summary: str | None
    result_json: dict[str, Any] | None
    report_url: str | None
    attempts: int
    max_attempts: int
    last_error: str | None

    model_config = {"from_attributes": True}


class ClaimRequest(BaseModel):
    worker_id: str | None = None


class HeartbeatRequest(BaseModel):
    worker_id: str
    info: dict[str, Any] | None = None


class WorkerStatusItem(BaseModel):
    worker_id: str
    last_seen_at: datetime
    active: bool
    info: dict[str, Any] | None = None


class WorkerStatusResponse(BaseModel):
    any_active: bool
    workers: list[WorkerStatusItem]


class ApiKeyCreate(BaseModel):
    name: str
    scope: Scope


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    scope: Scope
    created_at: datetime
    last_used_at: datetime | None
    is_active: bool

    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    scope: Scope
    api_key: str


class AutomationControlPatch(BaseModel):
    scope: Scope | None = None
    title: str | None = None
    description: str | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class AutomationControlOut(BaseModel):
    key: str
    scope: Scope | None
    title: str
    description: str | None
    enabled: bool
    config: dict[str, Any]
    updated_at: datetime
    updated_by: str | None

    model_config = {"from_attributes": True}
