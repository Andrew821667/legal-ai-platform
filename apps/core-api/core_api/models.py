from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core_api.db import Base


class Scope(str, enum.Enum):
    bot = "bot"
    news = "news"
    worker = "worker"
    admin = "admin"


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    user = "user"


class LeadSource(str, enum.Enum):
    telegram_bot = "telegram_bot"
    website_form = "website_form"
    telegram_channel = "telegram_channel"
    miniapp_form = "miniapp_form"


class LeadSegment(str, enum.Enum):
    inhouse = "inhouse"
    law_firm = "law_firm"
    entrepreneur = "entrepreneur"
    other = "other"


class LeadStatus(str, enum.Enum):
    new = "new"
    qualified = "qualified"
    booked = "booked"
    proposal = "proposal"
    won = "won"
    lost = "lost"


class LegalClientType(str, enum.Enum):
    company = "company"
    entrepreneur = "entrepreneur"
    individual = "individual"
    unknown = "unknown"


class LegalArea(str, enum.Enum):
    contracts = "contracts"
    disputes = "disputes"
    corporate = "corporate"
    employment = "employment"
    tax_compliance = "tax_compliance"
    real_estate = "real_estate"
    it_ip_data = "it_ip_data"
    family_inheritance = "family_inheritance"
    debt_bankruptcy = "debt_bankruptcy"
    other = "other"


class LegalUrgency(str, enum.Enum):
    urgent = "urgent"
    high = "high"
    normal = "normal"
    no_deadline = "no_deadline"


class LegalIntakeStatus(str, enum.Enum):
    received = "received"
    needs_clarification = "needs_clarification"
    conflict_check = "conflict_check"
    scope_preparation = "scope_preparation"
    proposal_sent = "proposal_sent"
    accepted = "accepted"
    declined = "declined"
    closed = "closed"


class ConflictCheckStatus(str, enum.Enum):
    unchecked = "unchecked"
    clear = "clear"
    potential = "potential"
    conflict = "conflict"


class SpecialConsultationOrderSource(str, enum.Enum):
    lead_bot = "lead_bot"
    web = "web"
    admin = "admin"


class SpecialConsultationOrderStatus(str, enum.Enum):
    requested = "requested"
    awaiting_quote = "awaiting_quote"
    awaiting_payment = "awaiting_payment"
    paid = "paid"
    fulfilled = "fulfilled"
    cancelled = "cancelled"
    refunded = "refunded"


class PaymentProvider(str, enum.Enum):
    manual = "manual"
    yookassa = "yookassa"
    telegram = "telegram"


class PaymentTransactionStatus(str, enum.Enum):
    created = "created"
    pending = "pending"
    requires_action = "requires_action"
    paid = "paid"
    failed = "failed"
    cancelled = "cancelled"
    refunded = "refunded"


class ScheduledPostStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    ready = "ready"
    scheduled = "scheduled"
    publishing = "publishing"
    posted = "posted"
    failed = "failed"


class PostFeedbackSource(str, enum.Enum):
    comment = "comment"
    reaction_count = "reaction_count"
    reaction = "reaction"


class ContractJobStatus(str, enum.Enum):
    new = "new"
    processing = "processing"
    done = "done"
    failed = "failed"


class InputMode(str, enum.Enum):
    text_only = "text_only"
    file_url = "file_url"
    file_upload_reference = "file_upload_reference"


class ActorType(str, enum.Enum):
    user = "user"
    api_key = "api_key"
    system = "system"


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[Scope] = mapped_column(Enum(Scope, name="scope_enum"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa_text("true"))


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role_enum"), nullable=False)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    consent_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_revoked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false")
    )
    consent_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transborder_consent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false")
    )
    transborder_consent_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    marketing_consent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false")
    )
    marketing_consent_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    conversation_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cta_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cta_shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    cta_shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_interaction: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_users_telegram_id",
            "telegram_id",
            unique=True,
            postgresql_where=sa_text("telegram_id IS NOT NULL"),
        ),
        Index("ix_users_last_interaction", "last_interaction"),
        Index("ix_users_consent_revoked", "consent_revoked"),
    )


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source: Mapped[LeadSource] = mapped_column(Enum(LeadSource, name="lead_source_enum"), nullable=False)
    legacy_lead_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    segment: Mapped[LeadSegment | None] = mapped_column(
        Enum(LeadSegment, name="lead_segment_enum"), nullable=True
    )
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status_enum"), nullable=False, default=LeadStatus.new
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature: Mapped[str | None] = mapped_column(String(20), nullable=True)
    service_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specific_need: Mapped[str | None] = mapped_column(Text, nullable=True)
    pain_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget: Mapped[str | None] = mapped_column(String(255), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    conversation_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cta_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cta_shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    lead_magnet_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead_magnet_delivered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_leads_last_activity_at", "last_activity_at"),
        Index(
            "ix_leads_legacy_lead_id",
            "legacy_lead_id",
            unique=True,
            postgresql_where=sa_text("legacy_lead_id IS NOT NULL"),
        ),
        Index(
            "ix_leads_telegram_user_id",
            "telegram_user_id",
            postgresql_where=sa_text("telegram_user_id IS NOT NULL"),
        ),
        Index("ix_leads_status", "status"),
        Index("ix_leads_temperature", "temperature"),
    )


class NdaSignature(Base):
    """Подписание соглашения о конфиденциальности простой электронной подписью.

    Подпись — это нажатие кнопки в боте. Чтобы она чего-то стоила при споре,
    фиксируется не сам факт, а обстоятельства: кто, когда, какой именно текст
    видел. Хеш текста здесь ключевой — без него нельзя доказать, что документ
    не менялся после подписания.

    Запись одна на клиента: подписанное соглашение действует на все дальнейшие
    обращения, повторно подписывать не нужно.
    """

    __tablename__ = "nda_signatures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Кем подписано: аккаунт Telegram подтверждает канал, но не личность.
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Что подписано: версия и хеш текста, который клиент видел на экране.
    document_version: Mapped[str] = mapped_column(String(32), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Откуда пришло подписание — на случай появления других каналов.
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="telegram_bot")

    __table_args__ = (
        Index("ix_nda_signatures_lead", "lead_id"),
        Index("ix_nda_signatures_signed_at", "signed_at"),
    )


class LegalIntake(Base):
    __tablename__ = "legal_intakes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    client_type: Mapped[LegalClientType] = mapped_column(
        Enum(LegalClientType, name="legal_client_type_enum"),
        nullable=False,
        default=LegalClientType.unknown,
    )
    legal_area: Mapped[LegalArea] = mapped_column(
        Enum(LegalArea, name="legal_area_enum"),
        nullable=False,
        default=LegalArea.other,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[LegalUrgency] = mapped_column(
        Enum(LegalUrgency, name="legal_urgency_enum"),
        nullable=False,
        default=LegalUrgency.no_deadline,
    )
    deadline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_context: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[LegalIntakeStatus] = mapped_column(
        Enum(LegalIntakeStatus, name="legal_intake_status_enum"),
        nullable=False,
        default=LegalIntakeStatus.received,
    )
    conflict_status: Mapped[ConflictCheckStatus] = mapped_column(
        Enum(ConflictCheckStatus, name="conflict_check_status_enum"),
        nullable=False,
        default=ConflictCheckStatus.unchecked,
    )
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Первое обращение к клиенту от лица команды. Отметка о времени нужна,
    # чтобы фоновая задача не написала одному человеку дважды: она разбирает
    # обращения пачками и может перезапуститься на середине.
    outreach_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Причина, по которой связаться не удалось: у обращений с сайта нет
    # Telegram, а бот не может написать первым тому, кто ему не писал.
    outreach_blocked_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_legal_intakes_status_created", "status", "created_at"),
        Index("ix_legal_intakes_urgency_created", "urgency", "created_at"),
        Index("ix_legal_intakes_area", "legal_area"),
    )


class IntakeClarification(Base):
    """Ответ клиента на уточняющий вопрос ассистента.

    Хранится в основной базе, а не в состоянии бота: это материалы обращения,
    и они должны пережить перезапуск бота, смену устройства и передачу дела
    другому юристу.

    Вопрос сохраняется текстом целиком, а не только ключом. Формулировки со
    временем меняются, и через полгода по одному ключу будет не восстановить,
    на что именно отвечал человек.
    """

    __tablename__ = "intake_clarifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intake_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_intakes.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    question_key: Mapped[str] = mapped_column(String(64), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_intake_clarifications_intake", "intake_id", "created_at"),
        # Повторный ответ на тот же вопрос заменяет прежний, а не добавляет
        # вторую строку: иначе в карточке обращения будут противоречащие
        # ответы без признака, какой из них актуален.
        UniqueConstraint("intake_id", "question_key", name="uq_intake_clarification_question"),
    )


class IntakeDocument(Base):
    """Документ, присланный клиентом по обращению.

    Сам файл остаётся в Telegram — здесь только ссылка на него и
    обстоятельства передачи. Выкачивать и хранить материалы дела у себя без
    отдельного решения о том, где и сколько они лежат, было бы хуже: это
    персональные данные, и срок их хранения нужно определять осознанно.

    Отметка о соглашении фиксируется на момент передачи. Клиент может
    подписать NDA позже, но документ он передавал в других условиях, и в
    карточке это должно быть видно.
    """

    __tablename__ = "intake_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intake_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_intakes.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    telegram_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nda_signed_at_upload: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false")
    )

    __table_args__ = (
        Index("ix_intake_documents_intake", "intake_id", "created_at"),
    )


class SpecialConsultationProduct(Base):
    __tablename__ = "special_consultation_products"

    code: Mapped[str] = mapped_column(String(120), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB", server_default=sa_text("'RUB'"))
    base_price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_manual_quote: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa_text("true")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa_text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    highlights: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=sa_text("'[]'::jsonb")
    )
    fulfillment_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_special_consultation_products_active_sort", "is_active", "sort_order"),
    )


class SpecialConsultationOrder(Base):
    __tablename__ = "special_consultation_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    product_code: Mapped[str] = mapped_column(
        String(120), ForeignKey("special_consultation_products.code"), nullable=False
    )
    source: Mapped[SpecialConsultationOrderSource] = mapped_column(
        Enum(SpecialConsultationOrderSource, name="special_consultation_order_source_enum"),
        nullable=False,
    )
    status: Mapped[SpecialConsultationOrderStatus] = mapped_column(
        Enum(SpecialConsultationOrderStatus, name="special_consultation_order_status_enum"),
        nullable=False,
        default=SpecialConsultationOrderStatus.requested,
        server_default=sa_text("'requested'"),
    )
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_company: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB", server_default=sa_text("'RUB'"))
    amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    context: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb")
    )

    __table_args__ = (
        Index("ix_special_consultation_orders_created", "created_at"),
        Index("ix_special_consultation_orders_status_created", "status", "created_at"),
        Index(
            "ix_special_consultation_orders_lead",
            "lead_id",
            postgresql_where=sa_text("lead_id IS NOT NULL"),
        ),
        Index(
            "ix_special_consultation_orders_telegram_user_id",
            "telegram_user_id",
            postgresql_where=sa_text("telegram_user_id IS NOT NULL"),
        ),
    )


class SpecialConsultationPayment(Base):
    __tablename__ = "special_consultation_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("special_consultation_orders.id"), nullable=False
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        Enum(PaymentProvider, name="payment_provider_enum"),
        nullable=False,
    )
    status: Mapped[PaymentTransactionStatus] = mapped_column(
        Enum(PaymentTransactionStatus, name="payment_transaction_status_enum"),
        nullable=False,
        default=PaymentTransactionStatus.created,
        server_default=sa_text("'created'"),
    )
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB", server_default=sa_text("'RUB'"))
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmation_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb")
    )

    __table_args__ = (
        Index("ix_special_consultation_payments_order_created", "order_id", "created_at"),
        Index("ix_special_consultation_payments_status_created", "status", "created_at"),
        Index(
            "ux_special_consultation_payments_provider_payment_id",
            "provider",
            "provider_payment_id",
            unique=True,
            postgresql_where=sa_text("provider_payment_id IS NOT NULL"),
        ),
        Index(
            "ux_special_consultation_payments_external_reference",
            "external_reference",
            unique=True,
            postgresql_where=sa_text("external_reference IS NOT NULL"),
        ),
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_events_lead_id", "lead_id", postgresql_where=sa_text("lead_id IS NOT NULL")),
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_type_created_at", "type", "created_at"),
    )


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rubric: Mapped[str | None] = mapped_column(String(100), nullable=True)
    format_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cta_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ScheduledPostStatus] = mapped_column(
        Enum(ScheduledPostStatus, name="scheduled_post_status_enum"),
        nullable=False,
        default=ScheduledPostStatus.scheduled,
    )
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_scheduled_posts_publish",
            "publish_at",
            postgresql_where=sa_text("status = 'scheduled'"),
        ),
        Index(
            "ix_scheduled_posts_source_hash",
            "source_hash",
            unique=True,
            postgresql_where=sa_text("source_hash IS NOT NULL"),
        ),
        Index(
            "ix_scheduled_posts_telegram_message_id",
            "telegram_message_id",
            postgresql_where=sa_text("telegram_message_id IS NOT NULL"),
        ),
    )


class ReaderPreference(Base):
    __tablename__ = "reader_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    topics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default=sa_text("'[]'::jsonb"))
    digest_frequency: Mapped[str] = mapped_column(
        String(50), nullable=False, default="never", server_default=sa_text("'never'")
    )
    expertise_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    miniapp_onboarding_done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false")
    )
    miniapp_audience: Mapped[str | None] = mapped_column(String(30), nullable=True)
    miniapp_interests: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=sa_text("'[]'::jsonb")
    )
    miniapp_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    miniapp_last_action: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_reader_preferences_telegram_user_id", "telegram_user_id", unique=True),
    )


class ReaderSavedPost(Base):
    __tablename__ = "reader_saved_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduled_posts.id"), nullable=False)

    __table_args__ = (
        Index("ix_reader_saved_posts_user_created", "telegram_user_id", "created_at"),
        Index("ix_reader_saved_posts_post_id", "post_id"),
        Index("ux_reader_saved_posts_user_post", "telegram_user_id", "post_id", unique=True),
    )


class ReaderMiniAppEvent(Base):
    __tablename__ = "reader_miniapp_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="miniapp", server_default=sa_text("'miniapp'"))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    screen: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_reader_miniapp_events_user_created", "telegram_user_id", "created_at"),
        Index("ix_reader_miniapp_events_type_created", "event_type", "created_at"),
        Index("ix_reader_miniapp_events_source_created", "source", "created_at"),
        Index("ix_reader_miniapp_events_action_created", "action", "created_at"),
    )


class ReaderEventRollup(Base):
    __tablename__ = "reader_event_rollups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default=sa_text("''"))
    cta_variant: Mapped[str] = mapped_column(
        String(50), nullable=False, default="v1_direct", server_default=sa_text("'v1_direct'")
    )
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        Index(
            "ux_reader_event_rollups_bucket_dims",
            "bucket_start",
            "channel",
            "source",
            "action",
            "cta_variant",
            unique=True,
        ),
        Index("ix_reader_event_rollups_bucket_channel", "bucket_start", "channel"),
        Index("ix_reader_event_rollups_variant_bucket", "cta_variant", "bucket_start"),
    )


class PostFeedbackSignal(Base):
    __tablename__ = "post_feedback_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduled_posts.id"), nullable=False)
    source: Mapped[PostFeedbackSource] = mapped_column(
        Enum(PostFeedbackSource, name="post_feedback_source_enum"),
        nullable=False,
    )
    signal_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    signal_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_post_feedback_signals_post_id", "post_id"),
        Index("ix_post_feedback_signals_created_at", "created_at"),
        Index(
            "ix_post_feedback_signals_message",
            "telegram_message_id",
            "telegram_chat_id",
            postgresql_where=sa_text("telegram_message_id IS NOT NULL"),
        ),
    )


class ContractJob(Base):
    __tablename__ = "contract_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ContractJobStatus] = mapped_column(
        Enum(ContractJobStatus, name="contract_job_status_enum"),
        nullable=False,
        default=ContractJobStatus.new,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_mode: Mapped[InputMode] = mapped_column(Enum(InputMode, name="input_mode_enum"), nullable=False)
    document_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_contract_jobs_queue",
            "priority",
            "created_at",
            postgresql_where=sa_text("status = 'new'"),
        ),
        Index(
            "ix_contract_jobs_stale",
            "updated_at",
            postgresql_where=sa_text("status = 'processing'"),
        ),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType, name="actor_type_enum"), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_audit_log_created", "created_at"),
        Index("ix_audit_log_target", "target_type", "target_id"),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (Index("ix_idempotency_keys_created", "created_at"),)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    info: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class WorkerActivity(Base):
    __tablename__ = "worker_activity"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_worker_activity_worker_time", "worker_id", "occurred_at"),
        Index("ix_worker_activity_action_time", "action", "occurred_at"),
    )


class AutomationControl(Base):
    __tablename__ = "automation_controls"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    scope: Mapped[Scope | None] = mapped_column(Enum(Scope, name="scope_enum"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa_text("true"))
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (Index("ix_automation_controls_scope", "scope"),)
