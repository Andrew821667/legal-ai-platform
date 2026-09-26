"""Запрос документов у клиента списком.

Юрист отмечает, что нужно (паспорт, договор, переписка), клиент получает
список в Telegram и видит его в кабинете, загружает файл в нужный пункт, а
юрист видит, чего не хватает.

Сообщение клиенту в Telegram — фоновое: при сбое связи журнал отправок сам
повторит его. Список при этом уже сохранён и виден в кабинете, так что
задержка сообщения ничего не теряет, а повтор не может прислать чужое.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api import telegram_delivery
from core_api.client_principal import cabinet_email
from core_api.models import DocumentRequest, Lead, LegalIntake

logger = logging.getLogger(__name__)

STATUSES = ("open", "received", "cancelled")
MAX_ITEMS = 20


def payload(row: DocumentRequest) -> dict:
    return {
        "request_id": str(row.id),
        "intake_id": str(row.intake_id),
        "title": row.title,
        "note": row.note,
        "status": row.status,
        "document_id": str(row.document_id) if row.document_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "received_at": row.received_at.isoformat() if row.received_at else None,
    }


def for_intakes(db: Session, intake_ids: Iterable[uuid.UUID], *, with_cancelled: bool = True) -> dict[uuid.UUID, list[dict]]:
    ids = list(intake_ids)
    if not ids:
        return {}
    stmt = select(DocumentRequest).where(DocumentRequest.intake_id.in_(ids))
    if not with_cancelled:
        stmt = stmt.where(DocumentRequest.status != "cancelled")
    grouped: dict[uuid.UUID, list[dict]] = {}
    for row in db.scalars(stmt.order_by(DocumentRequest.created_at, DocumentRequest.title)):
        grouped.setdefault(row.intake_id, []).append(payload(row))
    return grouped


def create(db: Session, intake: LegalIntake, titles: list[str], note: str | None) -> list[DocumentRequest]:
    """Новые пункты списка; уже ожидаемые с тем же названием не дублируются."""
    waiting = {
        title.casefold()
        for title in db.scalars(
            select(DocumentRequest.title).where(
                DocumentRequest.intake_id == intake.id, DocumentRequest.status == "open"
            )
        )
    }
    created: list[DocumentRequest] = []
    for raw in titles:
        title = " ".join(raw.split())[:200]
        if len(title) < 2 or title.casefold() in waiting:
            continue
        waiting.add(title.casefold())
        row = DocumentRequest(intake_id=intake.id, title=title, note=(note or "").strip()[:1000] or None)
        db.add(row)
        created.append(row)
    db.flush()
    return created


def mark(row: DocumentRequest, status: str, document_id: uuid.UUID | None = None) -> None:
    row.status = status
    row.document_id = document_id if status == "received" else None
    row.received_at = datetime.now(timezone.utc) if status == "received" else None


def fulfill(db: Session, intake_id: uuid.UUID, request_id: uuid.UUID, document_id: uuid.UUID) -> bool:
    """Загруженный файл закрывает пункт своего обращения; чужой пункт — нет."""
    row = db.get(DocumentRequest, request_id)
    if row is None or row.intake_id != intake_id or row.status == "cancelled":
        return False
    mark(row, "received", document_id)
    return True


def message_text(titles: list[str], note: str | None) -> str:
    lines = ["Юрист просит прислать документы по вашему обращению:", ""]
    lines += [f"• {title}" for title in titles]
    if note:
        lines += ["", note.strip()]
    lines += [
        "",
        "Пришлите их файлами в этот чат или загрузите в кабинете на сайте — "
        "в разделе «Мои дела» напротив каждого пункта. Паспорт и другие документы "
        "с персональными данными — только после подписания соглашения о конфиденциальности.",
    ]
    return "\n".join(lines)


def notify(lead: Lead, titles: list[str], note: str | None, *, transport=None) -> dict:
    """Сказать клиенту о списке: telegram, queued, not_configured, cabinet или none."""
    if lead.telegram_user_id:
        token = telegram_delivery._client_token()
        if token:
            try:
                telegram_delivery.send(
                    kind="document_request",
                    token=token,
                    chat_id=lead.telegram_user_id,
                    text=message_text(titles, note),
                    retryable=True,
                    lead_id=lead.id,
                    transport=transport,
                )
            except Exception as exc:  # noqa: BLE001 — исход уже в журнале, повторит фон
                logger.warning("document request notice failed: lead=%s %s", lead.id, telegram_delivery.safe_error(exc))
                return {"delivered_via": "queued"}
            return {"delivered_via": "telegram"}
        # Бот не настроен — сообщение не уйдёт, но список виден клиенту в
        # «Моих делах» мини-аппа.
        return {"delivered_via": "not_configured"}
    email = cabinet_email(lead)
    if email:
        return {"delivered_via": "cabinet", "cabinet_email": email}
    return {"delivered_via": "none"}
