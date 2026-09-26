"""Карточка клиента — одним ответом.

Экран открывается в мессенджере, часто с телефона и не всегда на быстрой
сети: десять последовательных запросов превратились бы в секунды ожидания.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api import case_stage, client_reviews, document_requests
from core_api.client_principal import cabinet_email
from core_api.db import get_db
from core_api.staff import is_staff
from core_api.models import (
    ClientReview,
    IntakeClarification,
    IntakeDocument,
    Lead,
    LegalIntake,
    NdaPersonalDataConsent,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    WorkAct,
)
from core_api.routers.lawyer_workspace.common import (
    _lead_title,
    _iso,
    _worked_without_agreement,
    _package_for,
    _intake_links_for,
)

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


@router.get("/clients/{lead_id}")
def client_card(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Всё по клиенту в одном ответе.

    Собирается разом, а не по частям: карточку открывают, чтобы вспомнить
    контекст перед разговором, и подгрузка блоков по очереди этому мешает.
    """
    _ = identity
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Client not found")

    intakes = db.execute(
        select(LegalIntake)
        .where(LegalIntake.lead_id == lead_id)
        .order_by(LegalIntake.created_at.desc())
    ).scalars().all()
    intake_ids = [item.id for item in intakes]

    clarifications: dict[uuid.UUID, list[dict]] = {}
    documents: dict[uuid.UUID, list[dict]] = {}
    requested = document_requests.for_intakes(db, intake_ids)
    if intake_ids:
        for row in db.execute(
            select(IntakeClarification)
            .where(IntakeClarification.intake_id.in_(intake_ids))
            .order_by(IntakeClarification.created_at)
        ).scalars().all():
            clarifications.setdefault(row.intake_id, []).append(
                {
                    "question": row.question_text,
                    "answer": row.answer_text,
                    "created_at": _iso(row.created_at),
                }
            )
        for row in db.execute(
            select(IntakeDocument)
            .where(IntakeDocument.intake_id.in_(intake_ids))
            .order_by(IntakeDocument.created_at)
        ).scalars().all():
            documents.setdefault(row.intake_id, []).append(
                {
                    "document_id": str(row.id),
                    "telegram_file_id": row.telegram_file_id,
                    "file_name": row.file_name,
                    "file_size": row.file_size,
                    "mime_type": row.mime_type,
                    "nda_signed_at_upload": row.nda_signed_at_upload,
                    "created_at": _iso(row.created_at),
                }
            )

    nda_checks = [NdaSignature.lead_id == lead_id]
    if lead.telegram_user_id is not None:
        nda_checks.append(NdaSignature.telegram_user_id == lead.telegram_user_id)
    nda = db.execute(
        select(NdaSignature)
        .where(or_(*nda_checks))
        .order_by(NdaSignature.signed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    nda_consent = (
        db.get(NdaPersonalDataConsent, nda.pdn_consent_id)
        if nda and nda.pdn_consent_id
        else None
    )

    agreements = db.execute(
        select(ServiceAgreement)
        .where(ServiceAgreement.lead_id == lead_id)
        .order_by(ServiceAgreement.created_at.desc())
    ).scalars().all()

    messages: dict[uuid.UUID, list[dict]] = {}
    if agreements:
        for row in db.execute(
            select(ServiceAgreementMessage)
            .where(ServiceAgreementMessage.agreement_id.in_([a.id for a in agreements]))
            .order_by(ServiceAgreementMessage.created_at)
        ).scalars().all():
            messages.setdefault(row.agreement_id, []).append(
                {
                    "role": row.role.value,
                    "text": row.text,
                    "created_at": _iso(row.created_at),
                }
            )

    acts: dict[uuid.UUID, list[dict]] = {}
    reviews: dict[uuid.UUID, ClientReview] = {}
    if agreements:
        reviews = {
            row.act_id: row
            for row in db.scalars(
                select(ClientReview)
                .join(WorkAct, WorkAct.id == ClientReview.act_id)
                .where(WorkAct.agreement_id.in_([a.id for a in agreements]))
            )
        }
    if agreements:
        for act in db.execute(
            select(WorkAct)
            .where(WorkAct.agreement_id.in_([a.id for a in agreements]))
            .order_by(WorkAct.created_at.desc())
        ).scalars().all():
            acts.setdefault(act.agreement_id, []).append(
                {
                    "act_id": str(act.id),
                    "act_number": act.act_number,
                    "kind": act.kind or "act",
                    "status": act.status.value,
                    "description_text": act.description_text,
                    "amount_minor": act.amount_minor,
                    "currency": act.currency,
                    "created_at": _iso(act.created_at),
                    "sent_at": _iso(act.sent_at),
                    "claimed_paid_at": _iso(act.claimed_paid_at),
                    "paid_at": _iso(act.paid_at),
                    "paid_note": act.paid_note,
                    "last_reminded_at": _iso(act.last_reminded_at),
                    "receipt_ref": act.receipt_ref,
                    "receipt_at": _iso(act.receipt_at),
                    "receipt_sent_at": _iso(act.receipt_sent_at),
                    "review": client_reviews.payload(reviews.get(act.id)),
                }
            )

    # Допсоглашения — под своим договором, а не отдельной строкой: иначе на
    # экране они выглядят вторым договором, а этап считался бы по ним.
    supplements: dict[uuid.UUID, list[ServiceAgreement]] = {}
    for item in agreements:
        if item.parent_agreement_id is not None:
            supplements.setdefault(item.parent_agreement_id, []).append(item)
    agreements = [item for item in agreements if item.parent_agreement_id is None]

    # Куда уйдёт документ: в Telegram, в кабинет (клиент без Telegram — вход
    # через Яндекс ID с этой почтой) или некуда.
    card_cabinet_email = cabinet_email(lead)

    def _agreement_row(item: ServiceAgreement) -> dict:
        return {
            "agreement_id": str(item.id),
            "delivery": "telegram" if item.client_telegram_user_id else ("cabinet" if card_cabinet_email else "none"),
            "cabinet_email": card_cabinet_email if not item.client_telegram_user_id else None,
            # Без этого при втором обращении клиента нельзя понять, к чему
            # относится договор: на экране они лежат одним списком.
            "intake_id": str(item.intake_id) if item.intake_id else None,
            "parent_agreement_id": str(item.parent_agreement_id) if item.parent_agreement_id else None,
            "number": item.agreement_number,
            "status": item.status.value,
            "template_kind": item.template_kind.value,
            "revision": item.revision,
            "subject": item.subject,
            "price_text": item.price_text,
            "amount_minor": item.amount_minor,
            "currency": item.currency,
            "payment_terms": item.payment_terms,
            "scope_text": item.scope_text,
            "exclusions_text": item.exclusions_text,
            "schedule_text": item.schedule_text,
            "expires_at": _iso(item.expires_at),
            "created_at": _iso(item.created_at),
            "sent_at": _iso(item.sent_at),
            "viewed_at": _iso(item.viewed_at),
            "last_reminded_at": _iso(item.last_reminded_at),
            "signed_at": _iso(item.signed_at),
            "declined_at": _iso(item.declined_at),
            # Клиент называет причину, когда отклоняет, — она писалась в
            # базу и нигде не читалась: юрист видел только дату отказа.
            "decline_reason": item.decline_reason,
            # Реквизиты, которые клиент ввёл при подписании: юристу они
            # нужны так же, как условия, — по ним видно, с кем договор.
            "client_snapshot": item.client_snapshot or {},
            "signer_position": item.signer_position,
            "authority_basis": item.authority_basis,
            "document_version": item.document_version,
            "messages": messages.get(item.id, []),
            "acts": acts.get(item.id, []),
            "supplements": [_agreement_row(row) for row in supplements.get(item.id, [])],
        }

    latest_agreement = agreements[0] if agreements else None
    # Договоры уже новыми вперёд: первый встреченный по обращению — последний.
    latest_by_intake: dict[uuid.UUID, ServiceAgreement] = {}
    for item in agreements:
        if item.intake_id is not None:
            latest_by_intake.setdefault(item.intake_id, item)
    return {
        "lead_id": str(lead.id),
        "name": _lead_title(lead),
        # Карточку архивного клиента открывают из архива — там свои кнопки.
        "archived_at": _iso(lead.archived_at),
        "is_test": is_staff(lead.telegram_user_id),
        **case_stage.fields(
            case_stage.stage_for(
                nda_signed=nda is not None,
                agreement_status=latest_agreement.status.value if latest_agreement else None,
                without_agreement=_worked_without_agreement(
                    [(item.without_agreement, item.status) for item in intakes]
                ),
            )
        ),
        "contact": lead.contact,
        "company": lead.company,
        "email": lead.email,
        "phone": lead.phone,
        "telegram_user_id": lead.telegram_user_id,
        # Почта, по которой клиент без Telegram увидит документы в кабинете.
        "cabinet_email": card_cabinet_email,
        "source": lead.source.value if lead.source else None,
        "created_at": _iso(lead.created_at),
        "nda": (
            {
                "signed_at": _iso(nda.signed_at),
                "signer_full_name": nda.signer_full_name,
                "signer_contact": nda.signer_contact,
                "signer_org": nda.signer_org,
                "identity_document_provided": bool(nda.signer_identity_document),
                "pdn_consent_at": _iso(nda_consent.accepted_at) if nda_consent else None,
                "pdn_consent_version": nda_consent.document_version if nda_consent else None,
                "pdn_consent_id": str(nda_consent.id) if nda_consent else None,
                "version": nda.document_version,
                "nda_id": str(nda.id),
            }
            if nda
            else None
        ),
        "intakes": [
            {
                "intake_id": str(item.id),
                "created_at": _iso(item.created_at),
                "legal_area": item.legal_area.value,
                "practice": item.practice.value,
                "category": item.category,
                "client_type": item.client_type.value,
                "urgency": item.urgency.value,
                "deadline": item.deadline,
                "deadline_at": _iso(item.deadline_at),
                "region": item.region,
                "status": item.status.value,
                "conflict_status": item.conflict_status.value,
                "description": item.description,
                "internal_note": item.internal_note,
                "without_agreement": item.without_agreement,
                "package": _package_for(db, item),
                "outreach_sent_at": _iso(item.outreach_sent_at),
                "outreach_blocked_reason": item.outreach_blocked_reason,
                "clarifications": clarifications.get(item.id, []),
                "documents": documents.get(item.id, []),
                "document_requests": requested.get(item.id, []),
                "links": _intake_links_for(db, item.id),
                # У постоянного клиента с двумя делами этап в шапке — по
                # последнему договору; у каждого обращения — свой, по его договорам.
                **case_stage.fields(
                    case_stage.stage_for(
                        nda_signed=nda is not None,
                        agreement_status=latest_by_intake[item.id].status.value
                        if item.id in latest_by_intake
                        else None,
                        without_agreement=item.without_agreement,
                    )
                ),
            }
            for item in intakes
        ],
        "agreements": [_agreement_row(item) for item in agreements],
    }
