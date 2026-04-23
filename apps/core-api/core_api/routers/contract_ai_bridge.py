"""
Contract AI Bridge — проксирование запросов к Contract-AI-System.

Позволяет:
- Проверять статус Contract-AI-System
- Отправлять файлы на анализ (от имени пользователя платформы)
- Получать SSO-токен для бесшовного входа в веб-кабинет
- Отслеживать прогресс и получать результаты
"""
from __future__ import annotations

import logging
from typing import Any

import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.config import get_settings
from core_api.models import Scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/contract-ai", tags=["contract-ai-bridge"])


def _bridge_headers() -> dict[str, str]:
    """Заголовки для запросов к Contract-AI-System."""
    secret = get_settings().contract_ai_bridge_secret
    return {"X-Bridge-Secret": secret}


def _check_bridge_configured() -> None:
    """Проверка что bridge настроен."""
    s = get_settings()
    if not s.contract_ai_bridge_secret:
        raise HTTPException(status_code=503, detail="Contract AI bridge not configured (no secret)")


# ─── GET /status ─────────────────────────────────────────────

@router.get("/status")
def contract_ai_status(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
) -> dict[str, Any]:
    """
    Проверка статуса Contract-AI-System.
    Возвращает режим (online/busy/offline) и capabilities.
    """
    _ = identity
    s = get_settings()

    if not s.contract_ai_bridge_status_url:
        return {"mode": s.contract_ai_bridge_mode, "source": "config", "version": "unknown"}

    try:
        resp = requests.get(
            s.contract_ai_bridge_status_url,
            headers=_bridge_headers(),
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {**data, "source": "live"}
        return {"mode": "offline", "source": "error", "status_code": resp.status_code}
    except requests.RequestException as e:
        logger.warning("Contract AI status check failed: %s", e)
        return {"mode": "offline", "source": "unreachable", "error": str(e)}


# ─── POST /sso ───────────────────────────────────────────────

@router.post("/sso")
def contract_ai_sso(
    user_email: str,
    user_name: str = "",
    org_id: str = "",
    role: str = "demo",
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
) -> dict[str, Any]:
    """
    Получить SSO-токен от Contract-AI-System.
    Возвращает JWT + redirect_url для бесшовного входа.
    """
    _ = identity
    _check_bridge_configured()
    s = get_settings()

    if not s.contract_ai_bridge_sso_url:
        raise HTTPException(status_code=503, detail="SSO URL not configured")

    try:
        resp = requests.post(
            s.contract_ai_bridge_sso_url,
            json={
                "platform_token": s.contract_ai_bridge_secret,
                "user_email": user_email,
                "user_name": user_name,
                "org_id": org_id,
                "role": role,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except requests.RequestException as e:
        logger.error("Contract AI SSO failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Contract AI unreachable: {e}") from e


# ─── POST /analyze ───────────────────────────────────────────

@router.post("/analyze")
def contract_ai_analyze(
    file: UploadFile = File(...),
    user_email: str = Form(...),
    user_name: str = Form(""),
    document_type: str = Form("contract"),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
) -> dict[str, Any]:
    """
    Отправить файл на анализ в Contract-AI-System.
    Возвращает job_id для отслеживания.
    """
    _ = identity
    _check_bridge_configured()
    s = get_settings()

    if not s.contract_ai_bridge_analysis_url:
        raise HTTPException(status_code=503, detail="Analysis URL not configured")

    try:
        resp = requests.post(
            s.contract_ai_bridge_analysis_url,
            headers=_bridge_headers(),
            files={"file": (file.filename, file.file, file.content_type)},
            data={
                "document_type": document_type,
                "user_email": user_email,
                "user_name": user_name,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except requests.RequestException as e:
        logger.error("Contract AI analyze failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Contract AI unreachable: {e}") from e


# ─── GET /progress/{job_id} ─────────────────────────────────

@router.get("/progress/{job_id}")
def contract_ai_progress(
    job_id: str,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
) -> dict[str, Any]:
    """Прогресс анализа."""
    _ = identity
    _check_bridge_configured()
    s = get_settings()

    if not s.contract_ai_bridge_progress_url:
        raise HTTPException(status_code=503, detail="Progress URL not configured")

    try:
        resp = requests.get(
            f"{s.contract_ai_bridge_progress_url}/{job_id}",
            headers=_bridge_headers(),
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Contract AI unreachable: {e}") from e


# ─── GET /result/{job_id} ───────────────────────────────────

@router.get("/result/{job_id}")
def contract_ai_result(
    job_id: str,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
) -> dict[str, Any]:
    """Полные результаты анализа."""
    _ = identity
    _check_bridge_configured()
    s = get_settings()

    if not s.contract_ai_bridge_result_url:
        raise HTTPException(status_code=503, detail="Result URL not configured")

    try:
        resp = requests.get(
            f"{s.contract_ai_bridge_result_url}/{job_id}",
            headers=_bridge_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Contract AI unreachable: {e}") from e


# ─── GET /result/{job_id}/summary ────────────────────────────

@router.get("/result/{job_id}/summary")
def contract_ai_summary(
    job_id: str,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
) -> dict[str, Any]:
    """Краткий текстовый отчёт (для Telegram)."""
    _ = identity
    _check_bridge_configured()
    s = get_settings()

    if not s.contract_ai_bridge_result_url:
        raise HTTPException(status_code=503, detail="Result URL not configured")

    try:
        resp = requests.get(
            f"{s.contract_ai_bridge_result_url}/{job_id}/summary",
            headers=_bridge_headers(),
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Contract AI unreachable: {e}") from e
