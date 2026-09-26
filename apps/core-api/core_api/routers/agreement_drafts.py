"""Черновик условий договора по обращению для рабочего места юриста.

Отдельным роутером, а не в lawyer_workspace: там и так всё рабочее место, а
здесь единственный вызов модели со своими таймаутом и отказами.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.config import get_settings
from core_api.db import get_db
from core_api.models import ActorType, AgreementTemplate, LegalIntake, Scope
from core_api.terms_draft import MAX_TEMPLATES, draft_terms

router = APIRouter(prefix="/api/v1/lawyer/intakes", tags=["lawyer-workspace"])


@router.post("/{intake_id}/terms-draft")
def terms_draft(
    intake_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Предложить поля формы договора по обращению и заготовкам юриста.

    Ничего не сохраняет: черновик уходит в форму, а договор составляет юрист.
    В журнал пишется только факт вызова, модель и стоимость — без текста.
    """
    intake = db.get(LegalIntake, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="Legal intake not found")

    settings = get_settings()
    if not settings.intake_analysis_api_key:
        raise HTTPException(status_code=503, detail="Terms draft is not configured")

    templates = list(
        db.scalars(
            select(AgreementTemplate)
            .where(or_(AgreementTemplate.practice.is_(None), AgreementTemplate.practice == intake.practice))
            .order_by(AgreementTemplate.use_count.desc(), AgreementTemplate.name)
            .limit(MAX_TEMPLATES)
        )
    )
    draft = draft_terms(
        intake,
        templates,
        api_key=settings.intake_analysis_api_key,
        base_url=settings.intake_analysis_base_url,
        model=settings.intake_analysis_model,
        proxy_url=settings.intake_analysis_proxy_url or None,
        timeout=settings.intake_analysis_timeout_seconds,
    )

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="legal_intake.terms_draft",
        target_type="legal_intake",
        target_id=intake.id,
        details={
            "ok": draft.ok,
            "error": draft.error,
            "model": draft.model,
            "cost_usd": round(draft.cost_usd, 6),
            "template_id": str(draft.template.id) if draft.template is not None else None,
        },
    )
    db.commit()

    if not draft.ok:
        raise HTTPException(status_code=502, detail="Model did not return a terms draft")

    return {
        "intake_id": str(intake.id),
        "fields": draft.fields,
        "amount_minor": draft.amount_minor,
        "template": (
            {"template_id": str(draft.template.id), "name": draft.template.name}
            if draft.template is not None
            else None
        ),
        "notes": draft.notes,
        "model": draft.model,
        "cost_usd": draft.cost_usd,
    }
