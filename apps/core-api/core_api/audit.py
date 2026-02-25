from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from core_api.models import ActorType, AuditLog


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
            details=details,
        )
    )
