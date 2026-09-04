"""
Мост синхронизации legacy lead-bot -> core-api.

Пока legacy остается основным runtime-контуром, bridge зеркалирует
подтвержденные лиды и события в новое ядро без влияния на UX бота.
"""

from __future__ import annotations

import json
import hashlib
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from config import get_config
import utils

logger = logging.getLogger(__name__)
config = get_config()


def _score_from_temperature(temperature: str | None) -> int | None:
    normalized = (temperature or "").strip().lower()
    if normalized == "hot":
        return 90
    if normalized == "warm":
        return 60
    if normalized == "cold":
        return 30
    return None


def _status_from_legacy(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    allowed = {"new", "qualified", "booked", "proposal", "won", "lost"}
    return normalized if normalized in allowed else "new"


def _build_contact_value(lead: dict, user_data: dict | None) -> str | None:
    if lead.get("phone"):
        return lead["phone"]
    if lead.get("email"):
        return lead["email"]
    username = (user_data or {}).get("username")
    if username:
        return f"@{username}"
    telegram_id = (user_data or {}).get("telegram_id")
    if telegram_id:
        return f"tg:{telegram_id}"
    return None


def _build_notes(lead: dict) -> str | None:
    notes = (lead.get("notes") or "").strip()
    return notes[:4000] if notes else None


def _stable_sync_key(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _build_user_name(user_data: dict) -> str | None:
    full_name = " ".join(
        part.strip() for part in [user_data.get("first_name") or "", user_data.get("last_name") or ""] if part.strip()
    )
    return full_name or None


class CoreApiBridge:
    def __init__(self) -> None:
        self.base_url = config.CORE_API_URL.rstrip("/")
        self.api_key = config.API_KEY_BOT
        self.timeout = config.CORE_API_TIMEOUT_SECONDS
        self.enabled = bool(config.CORE_API_SYNC_ENABLED and self.base_url and self.api_key)
        self.post_dedup_ttl = config.CORE_API_POST_DEDUP_TTL_SECONDS
        self._recent_post_successes: dict[str, float] = {}

    def _is_recent_duplicate(self, idempotency_key: str) -> bool:
        if self.post_dedup_ttl <= 0:
            return False
        now = time.monotonic()
        last_success_at = self._recent_post_successes.get(idempotency_key)
        if last_success_at is None:
            return False
        if (now - last_success_at) > self.post_dedup_ttl:
            self._recent_post_successes.pop(idempotency_key, None)
            return False
        return True

    def _remember_success(self, idempotency_key: str) -> None:
        if self.post_dedup_ttl <= 0:
            return
        self._recent_post_successes[idempotency_key] = time.monotonic()
        if len(self._recent_post_successes) > 512:
            oldest_key = min(self._recent_post_successes.items(), key=lambda item: item[1])[0]
            self._recent_post_successes.pop(oldest_key, None)

    def _get(self, path: str) -> Any:
        """Чтение из core-api. В отличие от _post не требует ключа идемпотентности."""
        if not self.enabled:
            return None
        request = urllib.request.Request(
            url=f"{self.base_url}{path}",
            method="GET",
            headers={"X-API-Key": self.api_key},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            logger.warning("Core API read failed [%s %s]", path, error.code)
        except Exception as error:
            logger.warning("Core API read error [%s]: %s", path, error)
        return None

    def _post(self, path: str, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        if self._is_recent_duplicate(idempotency_key):
            logger.debug("Skipping duplicate core-api post %s for %s", idempotency_key, path)
            return None

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
                "Idempotency-Key": idempotency_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                self._remember_success(idempotency_key)
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            payload_text = error.read().decode("utf-8", errors="ignore")
            logger.warning(
                "Core API sync failed [%s %s]: %s",
                path,
                error.code,
                utils.mask_sensitive_data(payload_text[:300]),
            )
        except Exception as error:
            logger.warning("Core API sync error [%s]: %s", path, error)
        return None

    def sync_lead(self, lead: dict, user_data: dict | None = None) -> str | None:
        if not self.enabled:
            return None

        payload = {
            "source": "telegram_bot",
            "legacy_lead_id": lead.get("id"),
            "telegram_user_id": (user_data or {}).get("telegram_id"),
            "name": lead.get("name") or (user_data or {}).get("first_name"),
            "contact": _build_contact_value(lead, user_data or {}),
            "company": lead.get("company"),
            "email": lead.get("email"),
            "phone": lead.get("phone"),
            "status": _status_from_legacy(lead.get("status")),
            "score": _score_from_temperature(lead.get("temperature")),
            "temperature": lead.get("temperature"),
            "service_category": lead.get("service_category"),
            "specific_need": lead.get("specific_need"),
            "pain_point": lead.get("pain_point"),
            "budget": lead.get("budget"),
            "urgency": lead.get("urgency"),
            "industry": lead.get("industry"),
            "conversation_stage": lead.get("conversation_stage"),
            "cta_variant": lead.get("cta_variant"),
            "cta_shown": bool(lead.get("cta_shown")),
            "lead_magnet_type": lead.get("lead_magnet_type"),
            "lead_magnet_delivered": bool(lead.get("lead_magnet_delivered")),
            "notes": _build_notes(lead),
        }
        result = self._post(
            "/api/v1/leads",
            payload,
            idempotency_key=_stable_sync_key("legacy-lead-sync", payload),
        )
        core_id = (result or {}).get("id")
        if core_id:
            logger.info("Legacy lead %s mirrored to core-api as %s", lead.get("id"), core_id)
        return core_id

    def create_legal_intake(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        """Create a dedicated legal-help intake in core-api."""
        return self._post(
            "/api/v1/legal-intakes",
            payload,
            idempotency_key=idempotency_key,
        )

    def list_intakes_pending_outreach(
        self,
        *,
        delay_minutes: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Обращения, которым пора написать от лица команды."""
        if not self.enabled:
            return []
        result = self._get(
            f"/api/v1/legal-intakes/outreach/pending?delay_minutes={delay_minutes}&limit={limit}"
        )
        return result if isinstance(result, list) else []

    def mark_intake_outreach(
        self,
        intake_id: str,
        *,
        blocked_reason: str | None = None,
    ) -> bool:
        """Фиксирует результат первого обращения к клиенту.

        Отметка обязательна и при отказе: иначе фоновая задача вернётся к
        обращению на следующем круге и напишет человеку повторно.
        """
        if not self.enabled:
            return False
        payload = {"blocked_reason": blocked_reason} if blocked_reason else {}
        key = f"outreach:{intake_id}:{blocked_reason or 'sent'}"
        return self._post(
            f"/api/v1/legal-intakes/{intake_id}/outreach", payload, idempotency_key=key
        ) is not None

    def record_clarification(
        self,
        intake_id: str,
        *,
        question_key: str,
        question_text: str,
        answer_text: str,
    ) -> bool:
        """Сохраняет ответ клиента на уточняющий вопрос.

        Ключ идемпотентности включает вопрос, но не ответ: если человек
        поправил себя, повтор должен пройти и заменить прежний ответ, а не
        отсеяться как дубликат.
        """
        if not self.enabled:
            return False
        return self._post(
            f"/api/v1/legal-intakes/{intake_id}/clarifications",
            {
                "question_key": question_key,
                "question_text": question_text,
                "answer_text": answer_text,
            },
            idempotency_key=_stable_sync_key(
                f"clarification:{intake_id}:{question_key}",
                {"answer": answer_text},
            ),
        ) is not None

    def record_intake_document(
        self,
        intake_id: str,
        *,
        telegram_file_id: str,
        file_name: str | None = None,
        file_size: int | None = None,
        mime_type: str | None = None,
        nda_signed_at_upload: bool = False,
    ) -> bool:
        """Регистрирует документ, присланный клиентом по обращению."""
        if not self.enabled:
            return False
        return self._post(
            f"/api/v1/legal-intakes/{intake_id}/documents",
            {
                "telegram_file_id": telegram_file_id,
                "file_name": file_name,
                "file_size": file_size,
                "mime_type": mime_type,
                "nda_signed_at_upload": nda_signed_at_upload,
            },
            idempotency_key=f"intake-doc:{intake_id}:{telegram_file_id}",
        ) is not None

    def assistant_turn(
        self,
        intake_id: str,
        *,
        history: list[dict[str, str]],
        base_questions: list[str],
        area_label: str,
        asked_count: int,
    ) -> dict[str, Any] | None:
        """Следующая реплика помощника в разговоре с клиентом.

        Модель вызывается на стороне core-api: ключ, прокси и учёт стоимости
        настроены там, и держать их в двух местах значило бы чинить доступ к
        вендору дважды.

        Ключ идемпотентности включает длину разговора: каждая реплика — это
        новый шаг, и отсеивать его как повтор нельзя.
        """
        if not self.enabled:
            return None
        return self._post(
            f"/api/v1/legal-intakes/{intake_id}/assistant/turn",
            {
                "history": history,
                "base_questions": base_questions,
                "area_label": area_label,
                "asked_count": asked_count,
            },
            idempotency_key=f"assistant-turn:{intake_id}:{len(history)}",
        )

    def get_nda_document(self) -> dict[str, Any] | None:
        """Текст соглашения с версией и контрольной суммой."""
        if not self.enabled:
            return None
        result = self._get("/api/v1/nda/document")
        return result if isinstance(result, dict) else None

    def get_nda_status(self, lead_id: str) -> dict[str, Any] | None:
        """Подписано ли соглашение этим клиентом."""
        if not self.enabled:
            return None
        result = self._get(f"/api/v1/nda/status/{lead_id}")
        return result if isinstance(result, dict) else None

    def sign_nda(
        self,
        *,
        lead_id: str,
        telegram_user_id: int | None,
        telegram_username: str | None,
        signer_name: str | None,
        document_hash: str,
    ) -> dict[str, Any] | None:
        """Фиксирует подписание соглашения простой электронной подписью.

        Версию документа проставляет сервер: он же отрисовывает текст, и только
        он знает, какая редакция действует в момент подписания.
        """
        if not self.enabled:
            return None
        return self._post(
            "/api/v1/nda/sign",
            {
                "lead_id": lead_id,
                "telegram_user_id": telegram_user_id,
                "telegram_username": telegram_username,
                "signer_name": signer_name,
                "document_hash": document_hash,
            },
            idempotency_key=f"nda-sign:{lead_id}",
        )

    def sync_user(self, user_data: dict) -> str | None:
        if not self.enabled:
            return None

        payload = {
            "role": "user",
            "telegram_id": user_data.get("telegram_id"),
            "username": user_data.get("username"),
            "first_name": user_data.get("first_name"),
            "last_name": user_data.get("last_name"),
            "name": _build_user_name(user_data),
            "consent_given": bool(user_data.get("consent_given")),
            "consent_date": user_data.get("consent_date"),
            "consent_revoked": bool(user_data.get("consent_revoked")),
            "consent_revoked_at": user_data.get("consent_revoked_at"),
            "transborder_consent": bool(user_data.get("transborder_consent")),
            "transborder_consent_date": user_data.get("transborder_consent_date"),
            "marketing_consent": bool(user_data.get("marketing_consent")),
            "marketing_consent_date": user_data.get("marketing_consent_date"),
            "conversation_stage": user_data.get("conversation_stage"),
            "cta_variant": user_data.get("cta_variant"),
            "cta_shown": bool(user_data.get("cta_shown")),
            "cta_shown_at": user_data.get("cta_shown_at"),
            "last_interaction": user_data.get("last_interaction"),
        }
        result = self._post(
            "/api/v1/users",
            payload,
            idempotency_key=_stable_sync_key("legacy-user-sync", payload),
        )
        core_id = (result or {}).get("id")
        if core_id:
            logger.info(
                "Legacy user %s mirrored to core-api as %s",
                utils.mask_telegram_id(user_data.get("telegram_id")),
                core_id,
            )
        return core_id

    def track_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        core_lead_id: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        event_payload = dict(payload)
        self._post(
            "/api/v1/events",
            {
                "lead_id": core_lead_id,
                "type": event_type,
                "payload": event_payload,
            },
            idempotency_key=idempotency_key,
        )


core_api_bridge = CoreApiBridge()
