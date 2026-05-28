# -*- coding: utf-8 -*-
"""
Revision compare API — produces a side-by-side report for two contract
revisions in JSON / xlsx / PDF, all driven by the same underlying
`RevisionComparator`.

Endpoints (mounted at `/api/v1/revisions` in main.py):

  POST  /compare        body: CompareRequest, query: ?format=json|xlsx|pdf
                        - json → application/json with the full report
                          (rows + summary). Used by the UI to render the
                          comparison table in-app.
                        - xlsx → file download (template-matched workbook).
                        - pdf  → file download (landscape A3, same look).

  GET   /{contract_id}  list available revisions of the given contract
                        — used by the UI dropdown «Сравнить с …».

JSON, xlsx, and PDF share the *exact same* data so what the lawyer
sees in the UI is byte-equivalent to what they download.
"""
from __future__ import annotations

import io
import re
import uuid
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.changes_models import ContractVersion
from src.models.database import get_db
from src.services.document_diff_service import DocumentDiffService
from src.services.document_parser import DocumentParser
from src.services.llm_gateway import LLMGateway
from src.services.revision_comparator import (
    Perspective,
    RevisionComparator,
    RevisionDiffReport,
)
from src.services.revision_pdf_exporter import export_report as pdf_export_report
from src.services.revision_xlsx_exporter import export_report as xlsx_export_report


class _ParserAdapter:
    """Adapt DocumentParser to the interface RevisionComparator expects.

    Comparator wants `extract_clauses(content) -> list[{number, title, text}]`,
    while DocumentParser exposes `_extract_sections_from_text` returning
    `[{title, type, paragraphs}]`. We pull the leading "1.2.3" out of the
    title to fill `number`, and flatten paragraphs into a single text.
    """

    _NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)")

    def __init__(self, inner: DocumentParser) -> None:
        self._inner = inner

    def parse(self, path: str) -> str:
        return self._inner.parse(path)

    def extract_clauses(self, content: str) -> list[dict[str, Any]]:
        sections = self._inner._extract_sections_from_text(content)
        out: list[dict[str, Any]] = []
        for s in sections:
            title = (s.get("title") or "").strip()
            m = self._NUMBER_RE.match(title)
            number = m.group(1) if m else None
            text = "\n".join(s.get("paragraphs", []) or []).strip()
            if number is None and not text:
                continue
            out.append({"number": number, "title": title, "text": text})
        return out


router = APIRouter()


# ---------- request / response schemas ------------------------------------

class CompareRequest(BaseModel):
    """Payload for POST /compare."""

    old_revision_id: int = Field(..., description="ID более ранней редакции")
    new_revision_id: int = Field(..., description="ID более поздней редакции")
    perspective: Perspective = Field(
        Perspective.NEUTRAL,
        description="С чьей точки зрения оценивать изменения",
    )
    title: Optional[str] = Field(
        None,
        description="Заголовок отчёта; если не задан — берётся имя файла новой редакции",
    )


class RevisionListItem(BaseModel):
    id: int
    version_number: int
    source: str
    description: Optional[str]
    is_current: bool
    file_name: str
    uploaded_at: Optional[str]


# ---------- helpers --------------------------------------------------------

def _load_revision(db: Session, revision_id: int) -> ContractVersion:
    rev = db.query(ContractVersion).filter(ContractVersion.id == revision_id).first()
    if rev is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ContractVersion {revision_id} not found",
        )
    return rev


def _read_content(version: ContractVersion, parser: _ParserAdapter) -> str:
    """Return parsed text content of the revision's file.

    Errors out with 422 if the file isn't readable — keeps the endpoint
    from silently producing an empty report.
    """
    file_path = Path(version.file_path or "")
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"ContractVersion {version.id} file is missing on disk",
        )
    try:
        return parser.parse(str(file_path))   # returns plain text
    except Exception as exc:
        logger.exception("Failed to parse revision %s file", version.id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse revision {version.id}: {exc}",
        )


def _label_for(version: ContractVersion) -> str:
    return f"Редакция №{version.version_number}"


def _file_name(version: ContractVersion) -> str:
    return Path(version.file_path or "").name or _label_for(version)


def _build_report(
    db: Session,
    req: CompareRequest,
) -> tuple[RevisionDiffReport, str, str]:
    """Load revisions, run the comparator, return (report, old_label, new_label)."""
    old = _load_revision(db, req.old_revision_id)
    new = _load_revision(db, req.new_revision_id)
    if old.id == new.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="old_revision_id and new_revision_id must differ",
        )

    parser = _ParserAdapter(DocumentParser())
    old_content = _read_content(old, parser)
    new_content = _read_content(new, parser)

    old_label = _label_for(old)
    new_label = _label_for(new)

    comparator = RevisionComparator(
        diff_service=DocumentDiffService(),
        llm_gateway=LLMGateway(),
        parser=parser,
        old_revision_label=old_label,
        new_revision_label=new_label,
    )

    report = comparator.compare(
        old_content,
        new_content,
        perspective=req.perspective,
        title=req.title or f"Сравнение редакций договора (v{old.version_number} → v{new.version_number})",
        old_file_name=_file_name(old),
        new_file_name=_file_name(new),
    )
    return report, old_label, new_label


def _tmp_path(suffix: str) -> Path:
    """Per-request temp file path, cleaned up by the OS."""
    import tempfile
    fd, path = tempfile.mkstemp(prefix=f"revision_compare_{uuid.uuid4().hex[:8]}_", suffix=suffix)
    import os
    os.close(fd)
    return Path(path)


# ---------- endpoints -----------------------------------------------------

@router.post(
    "/compare",
    summary="Сравнить две редакции договора (JSON / xlsx / PDF)",
    responses={
        200: {"description": "Сравнение, в формате `format`"},
        400: {"description": "Запрос некорректен"},
        404: {"description": "Одна из редакций не найдена"},
        422: {"description": "Файл редакции недоступен или не парсится"},
    },
)
def compare_revisions(
    req: CompareRequest,
    format: Literal["json", "xlsx", "pdf"] = Query("json"),
    db: Session = Depends(get_db),
) -> Any:
    report, old_label, new_label = _build_report(db, req)

    if format == "json":
        return JSONResponse(report.as_dict())

    if format == "xlsx":
        out = _tmp_path(".xlsx")
        xlsx_export_report(report, out, old_revision_label=old_label, new_revision_label=new_label)
        buffer = io.BytesIO(out.read_bytes())
        out.unlink(missing_ok=True)
        filename = f"revision_compare_v{req.old_revision_id}_v{req.new_revision_id}.xlsx"
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if format == "pdf":
        out = _tmp_path(".pdf")
        pdf_export_report(report, out, old_revision_label=old_label, new_revision_label=new_label)
        buffer = io.BytesIO(out.read_bytes())
        out.unlink(missing_ok=True)
        filename = f"revision_compare_v{req.old_revision_id}_v{req.new_revision_id}.pdf"
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown format: {format}",
    )


@router.get(
    "/{contract_id}",
    summary="Список редакций договора (для dropdown «сравнить с …»)",
    response_model=list[RevisionListItem],
)
def list_revisions(contract_id: str, db: Session = Depends(get_db)) -> list[RevisionListItem]:
    rows = (
        db.query(ContractVersion)
        .filter(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_number.asc())
        .all()
    )
    return [
        RevisionListItem(
            id=r.id,
            version_number=r.version_number,
            source=r.source or "unknown",
            description=r.description,
            is_current=bool(r.is_current),
            file_name=Path(r.file_path or "").name,
            uploaded_at=r.uploaded_at.isoformat() if r.uploaded_at else None,
        )
        for r in rows
    ]
