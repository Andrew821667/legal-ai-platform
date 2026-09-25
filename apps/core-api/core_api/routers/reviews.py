"""Отзывы клиентов для сайта — только одобренные и с согласием (см. client_reviews)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core_api import client_reviews
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import Scope

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.get("/public")
def public_reviews(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = identity
    return client_reviews.public(db)
