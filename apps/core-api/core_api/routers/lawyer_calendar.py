"""Сроки практики для подписки календаря (см. core_api.lawyer_calendar)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core_api import lawyer_calendar
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import Scope

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


@router.get("/calendar")
def calendar(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    _ = identity
    return {"events": lawyer_calendar.events(db)}
