from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from core_api.models import ActorType, AuditLog


def _json_safe(value: Any) -> Any:
    """Приводит детали к тому, что переживёт json.dumps.

    Колонка `details` — обычный JSON, а у engine нет своего сериализатора.
    Вызовы кладут туда изменённые поля как есть: enum, datetime, UUID — и
    первое же поле-дата (срок обращения) роняло весь запрос на коммите.
    Терять действие из-за формата даты в журнале — худший из исходов: журнал
    для того и нужен, чтобы ничего не терялось.
    """
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def write_audit(
    db: Session,
    actor_type: ActorType,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=_json_safe(details) if details is not None else None,
        )
    )
