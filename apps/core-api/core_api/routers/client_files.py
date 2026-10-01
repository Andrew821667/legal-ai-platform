"""Файлы по делу в нашей базе: результаты юриста клиенту и загрузки клиента из кабинета.

Раньше передать клиенту без Telegram результат работы (заключение, претензию,
письменный план) было нечем, а документы, загруженные клиентом в кабинете,
пересылались юристу в Telegram и жили там — на серверах за рубежом, хотя
трансграничной передачи у оператора нет (уведомление в РКН от 01.10.2026).

Содержимое шифруется тем же ключом, что и паспортные данные (core_api.pii):
в базе и её резервных копиях лежит только шифротекст. В Telegram о файле
сообщается без имени файла — в нём бывают фамилии.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from core_api import document_requests, pii, telegram_delivery
from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.client_notices import queue_notice
from core_api.client_principal import Principal, resolve
from core_api.config import get_settings
from core_api.db import get_db
from core_api.models import ActorType, CaseMessage, ClientFile, Lead, LegalIntake, NdaSignature, Scope

logger = logging.getLogger(__name__)

client = APIRouter(prefix="/api/v1/client-portal", tags=["client-portal"])
lawyer = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])

MAX_BYTES = 20 * 1024 * 1024
ALLOWED = {
    "pdf", "doc", "docx", "rtf", "odt", "txt",
    "xls", "xlsx", "csv", "ods",
    "jpg", "jpeg", "png", "heic", "webp",
    "zip",
}


def _clean_name(raw: str | None) -> str:
    name = re.sub(r"[\r\n\"\\/]", "_", (raw or "").strip())[:200]
    ext = re.search(r"\.([A-Za-z0-9]{1,5})$", name)
    if not name or not ext:
        raise HTTPException(status_code=422, detail="File must have an extension")
    if ext.group(1).lower() not in ALLOWED:
        raise HTTPException(status_code=422, detail="File type is not allowed")
    return name


async def _read(upload: UploadFile) -> tuple[str, bytes]:
    name = _clean_name(upload.filename)
    data = await upload.read(MAX_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="File is empty")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 20 MB")
    return name, data


def _encrypt(data: bytes) -> bytes:
    fernet = pii._fernet()
    if fernet is None:
        raise HTTPException(status_code=500, detail="Encryption key is not configured")
    return fernet.encrypt(data)


def _decrypt(row: ClientFile) -> bytes:
    fernet = pii._fernet()
    if fernet is None:
        raise HTTPException(status_code=500, detail="Encryption key is not configured")
    return fernet.decrypt(row.content)


def meta(row: ClientFile) -> dict:
    return {
        "id": str(row.id),
        "intake_id": str(row.intake_id) if row.intake_id else None,
        "direction": row.direction,
        "file_name": row.file_name,
        "mime_type": row.mime_type,
        "size": row.size,
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "downloaded_at": row.downloaded_at.isoformat() if row.downloaded_at else None,
    }


def for_intakes(db: Session, intake_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    """Файлы по делам — для сводки кабинета (без содержимого)."""
    if not intake_ids:
        return {}
    rows = db.scalars(
        select(ClientFile).where(ClientFile.intake_id.in_(intake_ids)).order_by(ClientFile.created_at)
    )
    found: dict[uuid.UUID, list[dict]] = {}
    for row in rows:
        found.setdefault(row.intake_id, []).append(meta(row))
    return found


def without_case(db: Session, lead_ids: list[uuid.UUID]) -> list[dict]:
    """Файлы клиента вне дела (юрист прислал до первого обращения)."""
    if not lead_ids:
        return []
    rows = db.scalars(
        select(ClientFile)
        .where(ClientFile.lead_id.in_(lead_ids), ClientFile.intake_id.is_(None))
        .order_by(ClientFile.created_at)
    )
    return [meta(row) for row in rows]


def _nda_signed(db: Session, principal: Principal) -> bool:
    """NDA подписан по любому из обращений клиента — как в сводке кабинета."""
    checks = [NdaSignature.lead_id.in_(principal.lead_ids)]
    if principal.telegram_user_id is not None:
        checks.append(NdaSignature.telegram_user_id == principal.telegram_user_id)
    return db.scalar(select(NdaSignature.id).where(or_(*checks)).limit(1)) is not None


def _download(row: ClientFile) -> Response:
    data = _decrypt(row)
    # Запасное имя для старых браузеров — латиницей; кириллическое идёт в filename*.
    ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", row.file_name)
    if not re.search(r"[A-Za-z0-9]", ascii_name.rsplit(".", 1)[0]):
        ascii_name = "document" + (f".{row.file_name.rsplit('.', 1)[1]}" if "." in row.file_name else "")
    return Response(
        content=data,
        media_type=row.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(row.file_name)}",
            "Cache-Control": "no-store",
        },
    )


def _store(db: Session, *, lead_id: uuid.UUID, intake_id: uuid.UUID | None, direction: str,
           name: str, mime: str | None, data: bytes, note: str | None) -> ClientFile:
    row = ClientFile(
        lead_id=lead_id, intake_id=intake_id, direction=direction, file_name=name,
        mime_type=(mime or "").strip()[:128] or None, size=len(data),
        sha256=hashlib.sha256(data).hexdigest(), content=_encrypt(data),
        note=(note or "").strip()[:1000] or None,
    )
    db.add(row)
    db.flush()
    return row


# ---- Клиент ---------------------------------------------------------------


@client.post("/cases/{intake_id}/files", status_code=status.HTTP_201_CREATED)
async def client_upload(
    intake_id: uuid.UUID,
    file: UploadFile = File(...),
    telegram_user_id: int | None = Form(default=None),
    client_account_id: uuid.UUID | None = Form(default=None),
    request_id: uuid.UUID | None = Form(default=None),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Документ от клиента из кабинета — в базу, юристу — уведомление без имени."""
    if telegram_user_id is None and client_account_id is None:
        raise HTTPException(status_code=400, detail="telegram_user_id or client_account_id is required")
    principal = resolve(db, telegram_user_id=telegram_user_id, client_account_id=client_account_id)
    intake = db.get(LegalIntake, intake_id)
    if intake is None or intake.lead_id not in principal.lead_ids:
        raise HTTPException(status_code=404, detail="Legal intake not found")
    if not _nda_signed(db, principal):
        raise HTTPException(status_code=409, detail="NDA must be signed before uploading documents")
    name, data = await _read(file)
    row = _store(db, lead_id=intake.lead_id, intake_id=intake.id, direction="from_client",
                 name=name, mime=file.content_type, data=data, note=None)
    fulfilled = document_requests.fulfill(db, intake.id, request_id, None) if request_id else False
    queue_notice(
        db,
        f"client-file:{row.id}",
        "📎 Клиент загрузил документ в кабинете. Он в рабочем месте — карточка клиента, раздел «Файлы».",
    )
    write_audit(db, actor_type=ActorType.api_key, actor_id=identity.name, action="client_file.upload",
                target_type="legal_intake", target_id=intake.id,
                details={"direction": "from_client", "size": row.size, "request_fulfilled": fulfilled})
    db.commit()
    return meta(row)


@client.get("/files/{file_id}")
def client_download(
    file_id: uuid.UUID,
    telegram_user_id: int | None = Query(default=None, gt=0),
    client_account_id: uuid.UUID | None = Query(default=None),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> Response:
    _ = identity
    if telegram_user_id is None and client_account_id is None:
        raise HTTPException(status_code=400, detail="telegram_user_id or client_account_id is required")
    principal = resolve(db, telegram_user_id=telegram_user_id, client_account_id=client_account_id)
    row = db.get(ClientFile, file_id)
    if row is None or row.lead_id not in principal.lead_ids:
        raise HTTPException(status_code=404, detail="File not found")
    if row.direction == "to_client" and row.downloaded_at is None:
        row.downloaded_at = datetime.now(timezone.utc)
        db.commit()
    return _download(row)


# ---- Юрист ----------------------------------------------------------------


@lawyer.get("/clients/{lead_id}/files")
def lawyer_list(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    _ = identity
    if db.get(Lead, lead_id) is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    rows = db.scalars(select(ClientFile).where(ClientFile.lead_id == lead_id).order_by(ClientFile.created_at))
    return {"files": [meta(row) for row in rows]}


@lawyer.post("/clients/{lead_id}/files", status_code=status.HTTP_201_CREATED)
async def lawyer_upload(
    lead_id: uuid.UUID,
    file: UploadFile = File(...),
    intake_id: uuid.UUID | None = Form(default=None),
    note: str | None = Form(default=None),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Результат работы клиенту: в кабинет, в переписку по делу; клиенту с
    Telegram — уведомление без имени файла (сам файл в Telegram не уходит)."""
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    if intake_id is not None:
        intake = db.get(LegalIntake, intake_id)
        if intake is None or intake.lead_id != lead.id:
            raise HTTPException(status_code=404, detail="Case not found")
    else:
        intake_id = db.scalar(
            select(LegalIntake.id).where(LegalIntake.lead_id == lead.id).order_by(LegalIntake.created_at.desc()).limit(1)
        )
    name, data = await _read(file)
    row = _store(db, lead_id=lead.id, intake_id=intake_id, direction="to_client",
                 name=name, mime=file.content_type, data=data, note=note)
    text = f"📎 Документ от юриста: «{name}»."
    if row.note:
        text += f"\n\n{row.note}"
    db.add(CaseMessage(lead_id=lead.id, intake_id=intake_id, author="lawyer", channel="workspace", text=text))
    write_audit(db, actor_type=ActorType.api_key, actor_id=identity.name, action="client_file.upload",
                target_type="lead", target_id=lead.id, details={"direction": "to_client", "size": row.size})
    db.commit()
    db.refresh(row)

    delivered = ["cabinet"]
    token = telegram_delivery._client_token()
    if lead.telegram_user_id and token:
        # Кнопка мини-аппа — inline: так он получает подписанный initData и
        # сразу открывает дела клиента (с reply-клавиатуры вход был бы пустым).
        cases_url = f"{get_settings().miniapp_public_base_url.rstrip('/')}/miniapp/cases"
        rows = [[{"text": "📂 Открыть мои дела", "web_app": {"url": cases_url}}]]
        if intake_id:
            rows.append([{"text": "✍️ Ответить по делу", "callback_data": f"case:{intake_id}"}])
        try:
            telegram_delivery.send(
                kind="case_file",
                token=token,
                chat_id=lead.telegram_user_id,
                # Без имени файла: в нём бывают фамилии, а Telegram — за рубежом.
                text="📎 Юрист прислал документ по вашему делу. Он в личном кабинете: кнопка ниже "
                     "или ai-verdict.ru/cabinet на сайте.",
                reply_markup=json.dumps({"inline_keyboard": rows}),
                retryable=True,
                lead_id=lead.id,
            )
            delivered.append("telegram_notice")
        except Exception as exc:  # noqa: BLE001 — файл уже в кабинете; повтор — из журнала отправок
            logger.warning("client file notice failed: %s", telegram_delivery.safe_error(exc))
    return {**meta(row), "delivered": delivered}


@lawyer.get("/files/{file_id}")
def lawyer_download(
    file_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> Response:
    _ = identity
    row = db.get(ClientFile, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    if row.direction == "from_client" and row.downloaded_at is None:
        row.downloaded_at = datetime.now(timezone.utc)
        db.commit()
    return _download(row)


@lawyer.delete("/files/{file_id}")
def lawyer_delete(
    file_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(ClientFile, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    write_audit(db, actor_type=ActorType.api_key, actor_id=identity.name, action="client_file.delete",
                target_type="lead", target_id=row.lead_id, details={"direction": row.direction})
    db.execute(delete(ClientFile).where(ClientFile.id == row.id))
    db.commit()
    return {"deleted": True}
