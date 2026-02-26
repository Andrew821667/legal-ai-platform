from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import ActorType, AutomationControl, Scope
from core_api.schemas import AutomationControlOut, AutomationControlPatch

router = APIRouter(prefix="/api/v1/automation-controls", tags=["automation-controls"])

_DEFAULT_CONTROLS: tuple[dict[str, Any], ...] = (
    {
        "key": "news.generate.enabled",
        "scope": Scope.news,
        "title": "Генерация контента (news.generate)",
        "description": "Ночная автогенерация контент-плана и постов из источников.",
        "enabled": True,
        "config": {},
    },
    {
        "key": "news.publish.enabled",
        "scope": Scope.news,
        "title": "Публикация в Telegram (news.publish)",
        "description": "Автопаблишер scheduled_posts в Telegram-канал.",
        "enabled": True,
        "config": {},
    },
    {
        "key": "news.digest.enabled",
        "scope": Scope.news,
        "title": "Недельный дайджест",
        "description": "Автоматическая генерация weekly digest слотов.",
        "enabled": True,
        "config": {},
    },
    {
        "key": "news.alert_slot.enabled",
        "scope": Scope.news,
        "title": "Вечерний alert-слот",
        "description": "Дополнительный срочный слот при high-urgency материалах.",
        "enabled": True,
        "config": {},
    },
    {
        "key": "lead_bot.autorespond.enabled",
        "scope": Scope.bot,
        "title": "Автоответы лид-бота",
        "description": "Автоматическая генерация ответов в лид-боте.",
        "enabled": True,
        "config": {},
    },
    {
        "key": "worker.autoclaim.enabled",
        "scope": Scope.worker,
        "title": "Автоклейм contract-jobs",
        "description": "Автозахват новых задач contract-worker-ом.",
        "enabled": True,
        "config": {},
    },
)
_DEFAULT_BY_KEY = {row["key"]: row for row in _DEFAULT_CONTROLS}


def _ensure_defaults(db: Session) -> int:
    existing = set(db.execute(select(AutomationControl.key)).scalars().all())
    created = 0
    for row in _DEFAULT_CONTROLS:
        if row["key"] in existing:
            continue
        db.add(
            AutomationControl(
                key=row["key"],
                scope=row["scope"],
                title=row["title"],
                description=row["description"],
                enabled=row["enabled"],
                config=row["config"],
                updated_by="system.bootstrap",
            )
        )
        created += 1
    if created:
        db.commit()
    return created


@router.get("", response_model=list[AutomationControlOut])
def list_automation_controls(
    scope: Scope | None = Query(default=None),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.news, Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[AutomationControl]:
    _ensure_defaults(db)

    if identity.scope != Scope.admin and scope is not None and scope != identity.scope:
        raise HTTPException(status_code=403, detail="Insufficient scope")

    effective_scope = scope
    if effective_scope is None and identity.scope != Scope.admin:
        effective_scope = identity.scope

    stmt = select(AutomationControl).order_by(AutomationControl.scope.asc(), AutomationControl.key.asc())
    if effective_scope is not None:
        stmt = stmt.where(or_(AutomationControl.scope == effective_scope, AutomationControl.scope.is_(None)))
    return list(db.execute(stmt).scalars().all())


@router.post("/bootstrap", response_model=dict[str, int])
def bootstrap_automation_controls(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    created = _ensure_defaults(db)
    if created:
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="automation_controls.bootstrap",
            target_type="automation_control",
            details={"created": created},
        )
        db.commit()
    return {"created": created}


@router.put("/{control_key}", response_model=AutomationControlOut)
def upsert_automation_control(
    control_key: str,
    payload: AutomationControlPatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.news, Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> AutomationControl:
    row = db.get(AutomationControl, control_key)
    created = False
    is_admin = identity.scope == Scope.admin

    if row is None and not is_admin:
        raise HTTPException(status_code=404, detail="Control not found")

    if row is not None and not is_admin:
        if row.scope != identity.scope:
            raise HTTPException(status_code=403, detail="Insufficient scope for this control")
        if payload.scope is not None or payload.title is not None or payload.description is not None:
            raise HTTPException(status_code=403, detail="Only enabled/config can be changed with scoped key")

    if row is None:
        template = _DEFAULT_BY_KEY.get(control_key)
        if template is None and payload.scope is None:
            raise HTTPException(status_code=400, detail="scope is required for custom control")
        row = AutomationControl(
            key=control_key,
            scope=payload.scope if payload.scope is not None else template["scope"],
            title=payload.title or (template["title"] if template else control_key),
            description=payload.description if payload.description is not None else (template["description"] if template else None),
            enabled=payload.enabled if payload.enabled is not None else (template["enabled"] if template else True),
            config=payload.config if payload.config is not None else (template["config"] if template else {}),
        )
        created = True
    else:
        if payload.scope is not None:
            row.scope = payload.scope
        if payload.title is not None:
            row.title = payload.title
        if payload.description is not None:
            row.description = payload.description
        if payload.enabled is not None:
            row.enabled = payload.enabled
        if payload.config is not None:
            row.config = payload.config

    row.updated_by = identity.name
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="automation_control.create" if created else "automation_control.update",
        target_type="automation_control",
        target_id=None,
        details={"key": control_key, **payload.model_dump(exclude_none=True)},
    )

    db.commit()
    db.refresh(row)
    return row
