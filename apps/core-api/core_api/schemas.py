from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from shared.schemas import ContractJobCreateBase, EventCreateBase, LeadCreateBase, ScheduledPostCreateBase

from core_api.models import (
    ContractJobStatus,
    InputMode,
    LeadSegment,
    LeadSource,
    LeadStatus,
    PostFeedbackSource,
    ScheduledPostStatus,
    Scope,
    UserRole,
)


class MessageResponse(BaseModel):
    message: str


class UserCreate(BaseModel):
    role: UserRole = UserRole.user
    telegram_id: int | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    name: str | None = None
    consent_given: bool = False
    consent_date: datetime | None = None
    consent_revoked: bool = False
    consent_revoked_at: datetime | None = None
    transborder_consent: bool = False
    transborder_consent_date: datetime | None = None
    marketing_consent: bool = False
    marketing_consent_date: datetime | None = None
    conversation_stage: str | None = None
    cta_variant: str | None = None
    cta_shown: bool = False
    cta_shown_at: datetime | None = None
    last_interaction: datetime | None = None


class UserPatch(BaseModel):
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    name: str | None = None
    consent_given: bool | None = None
    consent_date: datetime | None = None
    consent_revoked: bool | None = None
    consent_revoked_at: datetime | None = None
    transborder_consent: bool | None = None
    transborder_consent_date: datetime | None = None
    marketing_consent: bool | None = None
    marketing_consent_date: datetime | None = None
    conversation_stage: str | None = None
    cta_variant: str | None = None
    cta_shown: bool | None = None
    cta_shown_at: datetime | None = None
    last_interaction: datetime | None = None


class UserDataOperationOut(BaseModel):
    telegram_user_id: int
    users_updated: int = 0
    users_reset: int = 0
    users_deleted: int = 0
    leads_anonymized: int = 0
    leads_deleted: int = 0
    messages_deleted: int = 0
    events_deleted: int = 0
    notifications_deleted: int = 0
    chat_states_cleared: int = 0
    business_states_cleared: int = 0
    chat_states_deleted: int = 0
    business_states_deleted: int = 0


class UsersCountOut(BaseModel):
    total: int


class UserOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    role: UserRole
    telegram_id: int | None
    username: str | None
    first_name: str | None
    last_name: str | None
    email: str | None
    name: str | None
    consent_given: bool
    consent_date: datetime | None
    consent_revoked: bool
    consent_revoked_at: datetime | None
    transborder_consent: bool
    transborder_consent_date: datetime | None
    marketing_consent: bool
    marketing_consent_date: datetime | None
    conversation_stage: str | None
    cta_variant: str | None
    cta_shown: bool
    cta_shown_at: datetime | None
    last_interaction: datetime | None

    model_config = {"from_attributes": True}


class LeadCreate(LeadCreateBase):
    source: LeadSource
    segment: LeadSegment | None = None
    status: LeadStatus = LeadStatus.new


class LeadPatch(BaseModel):
    legacy_lead_id: int | None = None
    contact: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    segment: LeadSegment | None = None
    status: LeadStatus | None = None
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
    cta_shown: bool | None = None
    lead_magnet_type: str | None = None
    lead_magnet_delivered: bool | None = None
    notes: str | None = None


class LeadOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    source: LeadSource
    legacy_lead_id: int | None
    telegram_user_id: int | None
    name: str | None
    contact: str | None
    company: str | None
    email: str | None
    phone: str | None
    segment: LeadSegment | None
    status: LeadStatus
    score: int | None
    temperature: str | None
    service_category: str | None
    specific_need: str | None
    pain_point: str | None
    budget: str | None
    urgency: str | None
    industry: str | None
    conversation_stage: str | None
    cta_variant: str | None
    cta_shown: bool
    lead_magnet_type: str | None
    lead_magnet_delivered: bool
    notes: str | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    utm_content: str | None
    utm_term: str | None

    model_config = {"from_attributes": True}


class LeadStatsOut(BaseModel):
    total_leads: int
    new_leads: int
    qualified_leads: int
    booked_leads: int
    proposal_leads: int
    won_leads: int
    lost_leads: int
    telegram_bot_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    stage_discover: int
    stage_diagnose: int
    stage_qualify: int
    stage_propose: int
    stage_handoff: int


class EventCreate(EventCreateBase):
    lead_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    type: str = Field(min_length=1, max_length=100)


class EventOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    lead_id: uuid.UUID | None
    user_id: uuid.UUID | None
    type: str
    payload: dict[str, Any]

    model_config = {"from_attributes": True}


class ScheduledPostCreate(ScheduledPostCreateBase):
    publish_at: datetime
    status: ScheduledPostStatus = ScheduledPostStatus.scheduled


class ScheduledPostPatch(BaseModel):
    status: ScheduledPostStatus | None = None
    title: str | None = None
    text: str | None = None
    publish_at: datetime | None = None
    format_type: str | None = None
    cta_type: str | None = None
    telegram_message_id: int | None = None
    posted_at: datetime | None = None
    feedback_snapshot: dict[str, Any] | None = None
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
    format_type: str | None
    cta_type: str | None
    publish_at: datetime
    status: ScheduledPostStatus
    telegram_message_id: int | None
    posted_at: datetime | None
    feedback_snapshot: dict[str, Any] | None
    attempts: int
    max_attempts: int
    last_error: str | None

    model_config = {"from_attributes": True}


class PostFeedbackCreate(BaseModel):
    source: PostFeedbackSource
    signal_key: str | None = None
    signal_value: int = 0
    text: str | None = None
    telegram_chat_id: str | None = None
    telegram_message_id: int | None = None
    telegram_user_id: int | None = None
    actor_name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class PostFeedbackOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    post_id: uuid.UUID
    source: PostFeedbackSource
    signal_key: str | None
    signal_value: int
    text: str | None
    telegram_chat_id: str | None
    telegram_message_id: int | None
    telegram_user_id: int | None
    actor_name: str | None
    payload: dict[str, Any]

    model_config = {"from_attributes": True}


class ContractJobCreate(ContractJobCreateBase):
    lead_id: uuid.UUID | None = None
    deadline_at: datetime | None = None
    input_mode: InputMode


class ContractJobPatch(BaseModel):
    status: ContractJobStatus
    worker_id: str | None = None
    last_error: str | None = None


class ContractJobTouch(BaseModel):
    worker_id: str | None = None
    note: str | None = None
    progress_pct: int | None = Field(default=None, ge=0, le=100)


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


class ContractJobSummaryOut(BaseModel):
    total: int
    by_status: dict[str, int]
    new_retryable_count: int
    new_exhausted_count: int
    processing_stale_count: int
    failed_retryable_count: int
    failed_terminal_count: int
    new_oldest_created_at: datetime | None
    new_oldest_age_minutes: int | None
    done_last_hours_count: int
    window_hours: int
    stale_minutes: int


class ContractJobHistoryEntry(BaseModel):
    created_at: datetime
    actor_type: str
    actor_id: str
    action: str
    details: dict[str, Any] | None = None


class ContractJobHistoryResponse(BaseModel):
    job_id: uuid.UUID
    entries: list[ContractJobHistoryEntry]


class ContractJobBulkRetryOut(BaseModel):
    requested_limit: int
    matched_count: int
    retried_count: int
    retryable_only: bool
    dry_run: bool
    older_than_minutes: int | None = None
    job_ids: list[uuid.UUID]


class ContractJobFinalizeExhaustedOut(BaseModel):
    requested_limit: int
    matched_count: int
    finalized_count: int
    dry_run: bool
    job_ids: list[uuid.UUID]


class ContractJobOpsSampleItem(BaseModel):
    id: uuid.UUID
    status: ContractJobStatus
    priority: int
    attempts: int
    max_attempts: int
    worker_id: str | None
    created_at: datetime
    updated_at: datetime
    last_error: str | None

    model_config = {"from_attributes": True}


class ContractJobOpsSamples(BaseModel):
    stale_processing: list[ContractJobOpsSampleItem]
    failed_retryable: list[ContractJobOpsSampleItem]
    new_exhausted: list[ContractJobOpsSampleItem]


class ContractJobOpsActionCount(BaseModel):
    action: str
    count: int


class ContractJobOpsEventEntry(BaseModel):
    created_at: datetime
    actor_type: str
    actor_id: str
    action: str
    target_id: uuid.UUID | None
    details: dict[str, Any] | None = None


class ContractJobOpsOverviewOut(BaseModel):
    generated_at: datetime
    summary: ContractJobSummaryOut
    action_counts: list[ContractJobOpsActionCount]
    recent_events: list[ContractJobOpsEventEntry]
    samples: ContractJobOpsSamples
    window_hours: int
    stale_minutes: int
    sample_limit: int
    events_limit: int


class ContractJobMaintenanceActionOut(BaseModel):
    requested: bool
    matched_count: int
    applied_count: int
    requeued_count: int = 0
    failed_terminal_count: int = 0
    job_ids: list[uuid.UUID]


class ContractJobMaintenanceOut(BaseModel):
    generated_at: datetime
    dry_run: bool
    stale_minutes: int
    before_summary: ContractJobSummaryOut
    after_summary: ContractJobSummaryOut
    reset_stale: ContractJobMaintenanceActionOut
    finalize_exhausted_new: ContractJobMaintenanceActionOut
    retry_failed: ContractJobMaintenanceActionOut


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


class WorkerActivityEntry(BaseModel):
    occurred_at: datetime
    action: str
    details: dict[str, Any] | None = None


class WorkerActionCount(BaseModel):
    action: str
    count: int


class WorkerActivityResponse(BaseModel):
    worker_id: str
    active: bool
    last_seen_at: datetime | None
    window_hours: int
    startup_events: list[datetime]
    action_counts: list[WorkerActionCount]
    entries: list[WorkerActivityEntry]


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


class ReaderPreferencesPatch(BaseModel):
    telegram_user_id: int
    topics: list[str] | None = None
    digest_frequency: str | None = None
    expertise_level: str | None = None


class ReaderPreferencesOut(BaseModel):
    telegram_user_id: int
    topics: list[str]
    digest_frequency: str
    expertise_level: str | None
    updated_at: datetime


class ReaderMiniAppProfilePatch(BaseModel):
    telegram_user_id: int
    onboarding_done: bool | None = None
    audience: str | None = None
    interests: list[str] | None = None
    goal: str | None = None
    last_action: str | None = None
    sync_reader_topics: bool = True
    digest_frequency: str | None = None
    expertise_level: str | None = None


class ReaderMiniAppProfileOut(BaseModel):
    telegram_user_id: int
    onboarding_done: bool
    audience: str
    interests: list[str]
    goal: str | None
    last_action: str | None
    topics: list[str]
    digest_frequency: str
    expertise_level: str | None
    updated_at: datetime


class ReaderMiniAppEventCreate(BaseModel):
    telegram_user_id: int
    event_type: str = Field(min_length=1, max_length=100)
    source: str | None = None
    screen: str | None = None
    action: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    update_last_action: bool = True


class ReaderMiniAppEventOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    telegram_user_id: int
    event_type: str
    source: str
    screen: str | None
    action: str | None
    payload: dict[str, Any]

    model_config = {"from_attributes": True}


class ReaderMiniAppTopMetric(BaseModel):
    label: str
    count: int


class ReaderMiniAppTopUser(BaseModel):
    telegram_user_id: int
    count: int


class ReaderMiniAppEventsSummaryOut(BaseModel):
    hours: int
    total_events: int
    unique_users: int
    top_sources: list[ReaderMiniAppTopMetric]
    top_event_types: list[ReaderMiniAppTopMetric]
    top_screens: list[ReaderMiniAppTopMetric]
    top_actions: list[ReaderMiniAppTopMetric]
    top_users: list[ReaderMiniAppTopUser]
    recent_events: list[ReaderMiniAppEventOut]


class ReaderMiniAppDeepLinkCreate(BaseModel):
    telegram_user_id: int
    source: str = "reader_bot"
    screen: str | None = None
    action: str | None = None
    post_id: uuid.UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ReaderMiniAppDeepLinkOut(BaseModel):
    path: str
    url: str
    query: dict[str, str]


class ReaderContinueStateOut(BaseModel):
    telegram_user_id: int
    onboarding_done: bool
    audience: str
    interests: list[str]
    topics: list[str]
    goal: str | None
    last_action: str | None
    last_action_at: datetime | None
    updated_at: datetime
    saved_count: int
    recent_events_24h: int
    lead_intents_30d: int
    recommended_section: str
    recommended_screen: str
    recommended_reason: str


class ReaderFeedItem(BaseModel):
    id: uuid.UUID
    title: str | None
    text: str
    source_url: str | None
    rubric: str | None
    format_type: str | None
    cta_type: str | None
    publish_at: datetime
    posted_at: datetime | None
    feedback_snapshot: dict[str, Any] | None
    is_saved: bool = False


class ReaderSaveRequest(BaseModel):
    telegram_user_id: int
    post_id: uuid.UUID
    saved: bool = True


class ReaderSaveResponse(BaseModel):
    post_id: uuid.UUID
    saved: bool


class ReaderFeedbackCreate(BaseModel):
    telegram_user_id: int
    post_id: uuid.UUID
    signal_key: str | None = None
    signal_value: int = 0
    text: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ReaderCtaClickCreate(BaseModel):
    telegram_user_id: int
    post_id: uuid.UUID | None = None
    cta_type: str | None = None
    context: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ReaderLeadIntentCreate(BaseModel):
    telegram_user_id: int
    post_id: uuid.UUID | None = None
    intent_type: str
    message: str | None = None
    contact: str | None = None
    name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ReaderLeadIntentOut(BaseModel):
    lead_id: uuid.UUID
    created: bool


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
