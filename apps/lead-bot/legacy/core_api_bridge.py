"""
Мост синхронизации legacy lead-bot -> core-api.

Пока legacy остается основным runtime-контуром, bridge зеркалирует
подтвержденные лиды и события в новое ядро без влияния на UX бота.
"""

from __future__ import annotations

import json
import hashlib
import logging
import urllib.error
import urllib.request
from typing import Any

from config import Config
import utils

logger = logging.getLogger(__name__)
config = Config()


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

    def _post(self, path: str, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any] | None:
        if not self.enabled:
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
            logger.info("Legacy user %s mirrored to core-api as %s", user_data.get("telegram_id"), core_id)
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
