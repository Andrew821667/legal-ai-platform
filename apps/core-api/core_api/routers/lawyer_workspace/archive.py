"""Архив клиентов: убрать, вернуть, удалить совсем; обезличивание по сроку."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api import anonymization
from core_api.db import get_db
from core_api.staff import is_staff
from core_api.models import (
    ActorType,
    AuditLog,
    ContractJob,
    Event,
    Lead,
    LegalIntake,
    NdaPersonalDataConsent,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementStatus,
    SpecialConsultationOrder,
    SpecialConsultationPayment,
    WorkAct,
)
from core_api.routers.lawyer_workspace.common import (
    _lead_title,
    _iso,
)

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


# --- Архив клиентов -------------------------------------------------------
#
# «Удалить» в карточке — не удаление, а архив: клиент пропадает из списка,
# задач и денег, но из архива его можно вернуть. Удалить совсем можно только
# из архива — два шага, чтобы подписанный договор не исчез от одного касания.


def _client_footprint(db: Session, lead_id: uuid.UUID) -> dict:
    """Что лежит у клиента — чтобы перед удалением было видно, что пропадёт."""
    intake_ids = select(LegalIntake.id).where(LegalIntake.lead_id == lead_id)
    agreements = db.execute(
        select(ServiceAgreement.status, ServiceAgreement.parent_agreement_id).where(
            or_(ServiceAgreement.lead_id == lead_id, ServiceAgreement.intake_id.in_(intake_ids))
        )
    ).all()
    main = [status for status, parent in agreements if parent is None]
    return {
        "intakes": int(db.scalar(select(func.count()).select_from(intake_ids.subquery())) or 0),
        "agreements": len([s for s in main if s != ServiceAgreementStatus.superseded]),
        "signed_agreements": len([s for s in main if s == ServiceAgreementStatus.signed]),
        "acts": int(
            db.scalar(
                select(func.count(WorkAct.id))
                .join(ServiceAgreement, ServiceAgreement.id == WorkAct.agreement_id)
                .where(or_(ServiceAgreement.lead_id == lead_id, ServiceAgreement.intake_id.in_(intake_ids)))
            )
            or 0
        ),
        "nda_signed": db.scalar(select(func.count(NdaSignature.id)).where(NdaSignature.lead_id == lead_id)) > 0,
    }


def _lead_or_404(db: Session, lead_id: uuid.UUID) -> Lead:
    lead = db.execute(select(Lead).where(Lead.id == lead_id).with_for_update()).scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return lead


@router.get("/archive")
def archive(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Клиенты в архиве — последние убранные первыми."""
    _ = identity
    leads = db.scalars(
        select(Lead).where(Lead.archived_at.is_not(None)).order_by(Lead.archived_at.desc()).limit(200)
    ).all()
    return [
        {
            "lead_id": str(lead.id),
            "name": _lead_title(lead),
            "contact": lead.contact,
            "company": lead.company,
            "created_at": _iso(lead.created_at),
            "archived_at": _iso(lead.archived_at),
            "is_test": is_staff(lead.telegram_user_id),
            # Когда персональные данные обезличатся по сроку (152-ФЗ) — или уже.
            "anonymize_on": _iso(anonymization.planned_date(db, lead)),
            "anonymized_at": _iso(lead.anonymized_at),
            **_client_footprint(db, lead.id),
        }
        for lead in leads
    ]


@router.get("/anonymization")
def anonymization_preview(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Сколько клиентов и NDA ждут обезличивания по сроку — только числа."""
    _ = identity
    return anonymization.preview(db)


@router.post("/clients/{lead_id}/archive")
def archive_client(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    lead = _lead_or_404(db, lead_id)
    if lead.archived_at is None:
        lead.archived_at = datetime.now(timezone.utc)
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="lead.archive",
            target_type="lead",
            target_id=lead.id,
            details={},
        )
        db.commit()
    return {"lead_id": str(lead.id), "archived_at": _iso(lead.archived_at)}


@router.post("/clients/{lead_id}/restore")
def restore_client(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    lead = _lead_or_404(db, lead_id)
    if lead.archived_at is not None:
        lead.archived_at = None
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="lead.restore",
            target_type="lead",
            target_id=lead.id,
            details={"reason": "lawyer"},
        )
        db.commit()
    return {"lead_id": str(lead.id), "archived_at": None}


@router.delete("/clients/{lead_id}")
def purge_client(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Удалить клиента совсем — только из архива.

    Уходит всё, что относится к этому клиенту: обращения с уточнениями,
    документами и связями, договоры с допсоглашениями, перепиской и актами,
    NDA и согласие на обработку ПД, события, заказы консультаций и записи
    журнала о нём. Записи другого клиента с тем же Telegram не трогаются —
    удаляется только то, что привязано к этой карточке.

    В журнале остаётся одна запись — что клиент удалён и сколько чего было,
    без имени и контактов: иначе удаление было бы неполным.
    """
    lead = _lead_or_404(db, lead_id)
    if lead.archived_at is None:
        raise HTTPException(status_code=409, detail="Move the client to the archive first")

    footprint = _client_footprint(db, lead.id)
    intake_ids = list(db.scalars(select(LegalIntake.id).where(LegalIntake.lead_id == lead.id)))
    agreement_ids = list(
        db.scalars(
            select(ServiceAgreement.id).where(
                or_(
                    ServiceAgreement.lead_id == lead.id,
                    ServiceAgreement.intake_id.in_(intake_ids or [uuid.UUID(int=0)]),
                )
            )
        )
    )
    act_ids = list(
        db.scalars(select(WorkAct.id).where(WorkAct.agreement_id.in_(agreement_ids or [uuid.UUID(int=0)])))
    )
    order_ids = list(
        db.scalars(select(SpecialConsultationOrder.id).where(SpecialConsultationOrder.lead_id == lead.id))
    )
    none = [uuid.UUID(int=0)]

    db.execute(
        delete(AuditLog).where(
            or_(
                and_(AuditLog.target_type == "lead", AuditLog.target_id == lead.id),
                and_(AuditLog.target_type == "legal_intake", AuditLog.target_id.in_(intake_ids or none)),
                and_(AuditLog.target_type == "service_agreement", AuditLog.target_id.in_(agreement_ids or none)),
                and_(AuditLog.target_type == "work_act", AuditLog.target_id.in_(act_ids or none)),
                and_(
                    AuditLog.target_type == "special_consultation_order",
                    AuditLog.target_id.in_(order_ids or none),
                ),
            )
        )
    )
    if agreement_ids:
        # Акты и переписка уходят каскадом, допсоглашения — по ссылке на договор.
        db.execute(delete(WorkAct).where(WorkAct.agreement_id.in_(agreement_ids)))
        db.execute(delete(ServiceAgreementMessage).where(ServiceAgreementMessage.agreement_id.in_(agreement_ids)))
        db.execute(delete(ServiceAgreement).where(ServiceAgreement.id.in_(agreement_ids)))
    if order_ids:
        db.execute(delete(SpecialConsultationPayment).where(SpecialConsultationPayment.order_id.in_(order_ids)))
        db.execute(delete(SpecialConsultationOrder).where(SpecialConsultationOrder.id.in_(order_ids)))
    db.execute(delete(Event).where(Event.lead_id == lead.id))
    # Задания другого продукта (анализ договоров) не наши — только отвязываем.
    db.execute(update(ContractJob).where(ContractJob.lead_id == lead.id).values(lead_id=None))
    # NDA и согласие, обращения с уточнениями, документами и связями —
    # каскадом от клиента.
    db.execute(delete(NdaSignature).where(NdaSignature.lead_id == lead.id))
    db.execute(delete(NdaPersonalDataConsent).where(NdaPersonalDataConsent.lead_id == lead.id))
    db.execute(delete(LegalIntake).where(LegalIntake.lead_id == lead.id))
    db.execute(delete(Lead).where(Lead.id == lead.id))
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="lead.purge",
        target_type="lead",
        target_id=lead_id,
        details=footprint,
    )
    db.commit()
    return {"lead_id": str(lead_id), "deleted": footprint}
