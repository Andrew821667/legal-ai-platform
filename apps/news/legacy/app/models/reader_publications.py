"""
Compatibility model for reader bot over the new `scheduled_posts` table.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


@dataclass(frozen=True)
class DraftView:
    """Lightweight view used by existing reader handlers."""

    title: str
    content: str


class ReaderPublication(Base):
    """
    Maps reader bot feed to core-api scheduled posts.
    Expected source rows: status='posted'.
    """

    __tablename__ = "scheduled_posts"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)

    @property
    def published_at(self) -> datetime:
        """Compatibility alias used by legacy reader formatting."""
        return self.publish_at

    @property
    def draft(self) -> DraftView:
        """Compatibility object exposing title/content fields."""
        return DraftView(
            title=self.title or "Без заголовка",
            content=self.text or "",
        )

    @property
    def views(self) -> int:
        """Reader feed currently does not store view counts."""
        return 0

    @property
    def reactions(self) -> dict:
        """Reader feed currently does not store reaction stats."""
        return {}
