"""Модерация отзывов клиентов."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api import client_reviews
from core_api.db import get_db
from core_api.models import (
    ActorType,
    ClientReview,
    Scope,
)

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


@router.post("/reviews/{review_id}/{decision}")
def moderate_review(
    review_id: uuid.UUID,
    decision: str,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Юрист решает, показывать ли отзыв на сайте. Без согласия клиента — нельзя."""
    if decision not in ("approve", "hide"):
        raise HTTPException(status_code=404, detail="Not found")
    review = db.get(ClientReview, review_id, with_for_update=True)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if decision == "approve" and not (review.publish_consent and review.text):
        raise HTTPException(status_code=409, detail="Client did not allow publishing this review")
    review.status = "approved" if decision == "approve" else "hidden"
    review.moderated_at = datetime.now(timezone.utc)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action=f"client_review.{decision}",
        target_type="client_review",
        target_id=review.id,
    )
    db.commit()
    return client_reviews.payload(review)
