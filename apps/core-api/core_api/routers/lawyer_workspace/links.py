"""Связи между обращениями разных клиентов (главное, подчинённое, совместное)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import (
    ActorType,
    IntakeLink,
    IntakeLinkType,
    LegalIntake,
    Scope,
)

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


class IntakeLinkCreate(BaseModel):
    linked_intake_id: uuid.UUID | None = None
    linked_lead_id: uuid.UUID
    # Роль обращения из URL относительно связываемого — не тип связи как
    # таковой: "main"/"subordinate" описывают одну и ту же связь с разных
    # концов, а хранится она всегда как subordinate → main (см. IntakeLink).
    role: str
    note: str | None = Field(default=None, max_length=500)


_INTAKE_LINK_ROLES = {"main", "subordinate", "joint"}


@router.post("/intakes/{intake_id}/links")
def create_intake_link(
    intake_id: uuid.UUID,
    payload: IntakeLinkCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Пометить обращение как связанное с делом другого клиента.

    Найдено вживую: два обращения оказались одним и тем же имущественным
    спором с двух сторон, а проверка конфликта у каждого шла независимо.
    Связь — только пометка для контекста: договоры, NDA и документы каждого
    обращения остаются раздельными, это не слияние дел в одно.
    """
    intake = db.get(LegalIntake, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="Intake not found")

    if payload.role not in _INTAKE_LINK_ROLES:
        raise HTTPException(status_code=400, detail="Неизвестная роль связи")

    query = select(LegalIntake).where(LegalIntake.lead_id == payload.linked_lead_id)
    if payload.linked_intake_id:
        query = query.where(LegalIntake.id == payload.linked_intake_id)
    matches = db.scalars(query.limit(2)).all()
    if len(matches) > 1:
        raise HTTPException(status_code=409, detail="У клиента несколько обращений: выберите конкретное дело")
    linked_intake = matches[0] if matches else None
    if linked_intake is None:
        raise HTTPException(status_code=404, detail="У указанного клиента нет обращения")
    if linked_intake.id == intake_id:
        raise HTTPException(status_code=400, detail="Нельзя связать обращение само с собой")

    existing = db.execute(
        select(IntakeLink).where(
            or_(
                and_(
                    IntakeLink.intake_id == intake_id,
                    IntakeLink.linked_intake_id == linked_intake.id,
                ),
                and_(
                    IntakeLink.intake_id == linked_intake.id,
                    IntakeLink.linked_intake_id == intake_id,
                ),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Эти обращения уже связаны — сначала снимите старую связь"
        )

    # role="main" переворачивает пару: обращение из URL становится основным,
    # значит подчинённым (первым в строке) хранится связываемое.
    if payload.role == "main":
        row_intake_id, row_linked_intake_id = linked_intake.id, intake_id
        link_type = IntakeLinkType.subordinate
    elif payload.role == "subordinate":
        row_intake_id, row_linked_intake_id = intake_id, linked_intake.id
        link_type = IntakeLinkType.subordinate
    else:
        row_intake_id, row_linked_intake_id = intake_id, linked_intake.id
        link_type = IntakeLinkType.joint

    link = IntakeLink(
        intake_id=row_intake_id,
        linked_intake_id=row_linked_intake_id,
        link_type=link_type,
        note=(payload.note or "").strip() or None,
    )
    db.add(link)
    db.flush()
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="intake_link.create",
        target_type="legal_intake",
        target_id=intake_id,
        details={"linked_intake_id": str(linked_intake.id), "role": payload.role},
    )
    db.commit()
    return {"link_id": str(link.id)}


@router.delete("/intakes/links/{link_id}")
def delete_intake_link(
    link_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Снять связь. Обе стороны равноправны — годится id связи с любого конца."""
    link = db.get(IntakeLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="intake_link.delete",
        target_type="legal_intake",
        target_id=link.intake_id,
        details={"linked_intake_id": str(link.linked_intake_id), "link_type": link.link_type.value},
    )
    db.delete(link)
    db.commit()
    return {"ok": True}
