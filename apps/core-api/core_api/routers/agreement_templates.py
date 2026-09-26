"""Заготовки условий договора — для типовых услуг юриста.

Заготовка только заполняет форму договора в рабочем месте: сам договор
по-прежнему составляется из того, что в форме, и проверяется так же.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import AgreementTemplate, Practice, Scope

router = APIRouter(prefix="/api/v1/lawyer/agreement-templates", tags=["agreement-templates"])


class TemplateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    # Пусто — заготовка для любой практики.
    practice: Practice | None = None
    # Пределы — как у договора (AgreementCreate): заготовка не должна давать
    # то, что форма договора потом не примет.
    subject: str = Field(default="", max_length=4000)
    scope_text: str = Field(default="", max_length=6000)
    exclusions_text: str = Field(default="", max_length=2000)
    schedule_text: str = Field(default="", max_length=2000)
    price_text: str = Field(default="", max_length=500)
    amount_minor: int | None = Field(default=None, ge=0, le=10**13)
    payment_terms: str = Field(default="", max_length=2000)
    # Пакет услуг сайта, которому соответствует заготовка; пусто — ни одному.
    package_id: str | None = Field(default=None, max_length=64, pattern=r"^[a-z0-9_]*$")


def _payload(row: AgreementTemplate) -> dict:
    return {
        "template_id": str(row.id),
        "name": row.name,
        "practice": row.practice.value if row.practice else None,
        "subject": row.subject,
        "scope_text": row.scope_text,
        "exclusions_text": row.exclusions_text,
        "schedule_text": row.schedule_text,
        "price_text": row.price_text,
        "amount_minor": row.amount_minor,
        "payment_terms": row.payment_terms,
        "use_count": row.use_count,
        "package_id": row.package_id,
    }


def _get(db: Session, template_id: uuid.UUID) -> AgreementTemplate:
    row = db.get(AgreementTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return row


def _apply(row: AgreementTemplate, payload: TemplateIn) -> None:
    data = payload.model_dump()
    for key, value in data.items():
        # Практика — строковый enum: обрезка превратила бы её в простую строку.
        if isinstance(value, str) and not isinstance(value, Practice):
            value = value.strip()
        setattr(row, key, value)
    row.package_id = payload.package_id or None


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Уникальность пакета: вторая заготовка на тот же пакет сделала бы
        # выбор формы договора гаданием.
        raise HTTPException(status_code=409, detail="Package already has a template") from exc


@router.get("")
def list_templates(
    practice: Practice | None = Query(default=None),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Для практики обращения — её заготовки и общие; чаще используемые выше."""
    _ = identity
    stmt = select(AgreementTemplate)
    if practice is not None:
        stmt = stmt.where(or_(AgreementTemplate.practice.is_(None), AgreementTemplate.practice == practice))
    rows = db.scalars(
        stmt.order_by(AgreementTemplate.use_count.desc(), AgreementTemplate.name).limit(100)
    ).all()
    return [_payload(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    _ = identity
    row = AgreementTemplate()
    _apply(row, payload)
    db.add(row)
    _commit(db)
    return _payload(row)


@router.put("/{template_id}")
def update_template(
    template_id: uuid.UUID,
    payload: TemplateIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    _ = identity
    row = _get(db, template_id)
    _apply(row, payload)
    _commit(db)
    return _payload(row)


@router.delete("/{template_id}")
def delete_template(
    template_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    _ = identity
    db.delete(_get(db, template_id))
    db.commit()
    return {"template_id": str(template_id), "deleted": True}


@router.post("/{template_id}/used")
def mark_used(
    template_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Юрист подставил заготовку в форму — поднимаем её в списке."""
    _ = identity
    row = _get(db, template_id)
    row.use_count += 1
    row.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return {"template_id": str(template_id), "use_count": row.use_count}
