"""Лиды бота — только в ядре.

До этого лид из Telegram жил в двух местах: SQLite бота был источником, а
ядро — зеркалом, куда изменения доезжали «когда получится». Два хранилища
расходились: юрист менял статус в рабочем месте, а бот через минуту
переписывал его своим; лид без почты и телефона не попадал в очередь
уведомлений ни там, ни там. Теперь бот пишет и читает лиды только в ядре.

Обработчики бота по-прежнему держат в руках небольшой номер лида (`id`) и
локальный `user_id`: это не хранилище, а адресация — номер выдаёт ядро
(`legacy_lead_id`), а `user_id` восстанавливается по Telegram-аккаунту из
локальной таблицы пользователей. Ни одного содержательного поля лида в
SQLite больше не пишется.

Транспорт вынесен отдельно, чтобы тесты подменяли его на память, а не
поднимали ядро.
"""

from __future__ import annotations

import copy
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from config import get_config

config = get_config()
logger = logging.getLogger(__name__)

SOURCE = "telegram_bot"

# Поля лида, которые бот присылает; всё остальное в lead_data — служебное
# (имена из старых форм вроде lead_temperature разбираются отдельно).
LEAD_FIELDS = frozenset({
    "name", "email", "phone", "company", "pain_point", "budget", "urgency", "industry",
    "service_category", "specific_need", "temperature", "status", "notes",
    "conversation_stage", "cta_variant", "cta_shown",
    "lead_magnet_type", "lead_magnet_delivered",
    "notification_sent", "last_message_at",
    "team_size", "contracts_per_month", "contact",
})
_BOOL_FIELDS = ("cta_shown", "lead_magnet_delivered", "notification_sent")
_ALLOWED_STATUS = {"new", "qualified", "booked", "proposal", "won", "lost"}


class LeadStoreError(RuntimeError):
    """Ядро не подтвердило запись лида — терять её молча нельзя."""


class HttpCoreTransport:
    """HTTP к ядру с короткими повторами на сетевые сбои.

    Повторы только на «не дозвонился»: ответ с ошибкой (4xx/5xx) повторять
    бессмысленно, а вот рестарт ядра при деплое длится секунды — и сообщение
    клиента не должно из-за него пропасть.
    """

    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict | None, headers: dict[str, str]) -> Any:
        data = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"X-API-Key": self.api_key, "Content-Type": "application/json", **headers},
        )
        delays = (0.3, 1.0, 2.5)
        for attempt, delay in enumerate(delays + (None,)):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    return None
                detail = error.read().decode("utf-8", errors="ignore")[:300]
                raise LeadStoreError(f"core-api {method} {path} -> {error.code}: {detail}") from error
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if delay is None:
                    raise LeadStoreError(f"core-api unreachable: {method} {path}: {error}") from error
                logger.warning("core-api %s %s: %s (retry %s)", method, path, type(error).__name__, attempt + 1)
                time.sleep(delay)
        return None  # pragma: no cover — цикл всегда завершается return/raise

    def get(self, path: str, params: dict | None = None) -> Any:
        cleaned = {key: value for key, value in (params or {}).items() if value is not None}
        query = f"?{urllib.parse.urlencode(cleaned)}" if cleaned else ""
        return self._request("GET", f"{path}{query}", None, {})

    def post(self, path: str, body: dict, idempotency_key: str | None = None) -> Any:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        return self._request("POST", path, body, headers)


class CoreLeadStore:
    def __init__(
        self,
        *,
        local_user_by_id: Callable[[int], dict | None],
        local_user_by_telegram_id: Callable[[int], dict | None],
        transport: Any | None = None,
    ) -> None:
        self._local_user_by_id = local_user_by_id
        self._local_user_by_telegram_id = local_user_by_telegram_id
        self._transport = transport
        self._cache: dict[str, tuple[float, Any]] = {}
        self._user_ids: dict[int, int] = {}

    # --- транспорт -----------------------------------------------------

    @property
    def transport(self) -> Any:
        if self._transport is None:
            if not (config.CORE_API_URL and config.API_KEY_BOT):
                raise LeadStoreError("CORE_API_URL/API_KEY_BOT are not set: leads live in core-api only")
            self._transport = HttpCoreTransport(
                config.CORE_API_URL, config.API_KEY_BOT, config.CORE_API_TIMEOUT_SECONDS
            )
        return self._transport

    def use_transport(self, transport: Any | None) -> None:
        self._transport = transport
        self._cache.clear()

    def _get(self, path: str, params: dict | None = None) -> Any:
        """Чтение с коротким кэшем и «протухшим» запасом на время недоступности ядра."""
        key = json.dumps({"p": path, "q": params or {}}, sort_keys=True, default=str)
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and now - cached[0] <= config.CORE_API_CACHE_TTL_SECONDS:
            return copy.deepcopy(cached[1])
        try:
            payload = self.transport.get(path, params)
        except LeadStoreError as error:
            if cached and now - cached[0] <= config.CORE_API_STALE_CACHE_TTL_SECONDS:
                logger.warning("core-api read failed, serving stale lead data: %s", error)
                return copy.deepcopy(cached[1])
            logger.error("core-api read failed: %s", error)
            return None
        self._cache[key] = (now, copy.deepcopy(payload))
        if len(self._cache) > 256:
            oldest = min(self._cache.items(), key=lambda item: item[1][0])[0]
            self._cache.pop(oldest, None)
        return payload

    def _post(self, path: str, body: dict) -> Any:
        # Ключ — на вызов, а не на содержимое: повтор после обрыва связи не
        # заведёт второго лида, а два одинаковых по смыслу вызова — заведут.
        result = self.transport.post(path, body, idempotency_key=f"bot-lead-{uuid.uuid4().hex}")
        self._cache.clear()
        return result

    # --- адресация -----------------------------------------------------

    def _telegram_id(self, user_id: int) -> int:
        user = self._local_user_by_id(int(user_id))
        telegram_id = (user or {}).get("telegram_id")
        if not telegram_id:
            raise LeadStoreError(f"local user {user_id} has no telegram id")
        self._user_ids[int(telegram_id)] = int(user_id)
        return int(telegram_id)

    def _local_user_id(self, telegram_id: int | None) -> int | None:
        if not telegram_id:
            return None
        cached = self._user_ids.get(int(telegram_id))
        if cached is not None:
            return cached
        user = self._local_user_by_telegram_id(int(telegram_id))
        if not user:
            return None
        self._user_ids[int(telegram_id)] = int(user["id"])
        return int(user["id"])

    def _contact_for(self, lead_data: dict, user: dict | None) -> str | None:
        """Контакт для карточки: телефон или почта, иначе Telegram-аккаунт."""
        if lead_data.get("phone"):
            return str(lead_data["phone"])
        if lead_data.get("email"):
            return str(lead_data["email"])
        username = (user or {}).get("username")
        if username:
            return f"@{username}"
        telegram_id = (user or {}).get("telegram_id")
        return f"tg:{telegram_id}" if telegram_id else None

    # --- преобразования ---------------------------------------------------

    @staticmethod
    def payload_from_legacy(lead_data: dict | None) -> dict:
        """Поля лида в терминах ядра; None и чужие ключи выбрасываются."""
        data = dict(lead_data or {})
        if "lead_temperature" in data and not data.get("temperature"):
            data["temperature"] = data.pop("lead_temperature")
        payload: dict[str, Any] = {}
        for key, value in data.items():
            if key not in LEAD_FIELDS or value is None:
                continue
            if key in _BOOL_FIELDS:
                payload[key] = bool(value)
            elif key == "status":
                # Бот знает только «new», а статус двигает юрист в рабочем
                # месте: «new» от бота не должно откатывать «won».
                normalized = str(value).strip().lower()
                if normalized in _ALLOWED_STATUS and normalized != "new":
                    payload[key] = normalized
            elif key == "notes":
                payload[key] = str(value)[:4000]
            elif key == "last_message_at" and isinstance(value, datetime):
                payload[key] = value.isoformat()
            else:
                payload[key] = value
        return payload

    def lead_from_core(self, row: dict | None) -> dict | None:
        if not row:
            return None
        legacy_id = row.get("legacy_lead_id")
        return {
            "id": int(legacy_id) if legacy_id is not None else None,
            "core_lead_id": row.get("id"),
            "legacy_lead_id": legacy_id,
            "user_id": self._local_user_id(row.get("telegram_user_id")),
            "telegram_user_id": row.get("telegram_user_id"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "name": row.get("name"),
            "contact": row.get("contact"),
            "email": row.get("email"),
            "phone": row.get("phone"),
            "company": row.get("company"),
            "temperature": row.get("temperature"),
            "status": row.get("status"),
            "service_category": row.get("service_category"),
            "specific_need": row.get("specific_need"),
            "pain_point": row.get("pain_point"),
            "budget": row.get("budget"),
            "urgency": row.get("urgency"),
            "industry": row.get("industry"),
            "team_size": row.get("team_size"),
            "contracts_per_month": row.get("contracts_per_month"),
            "conversation_stage": row.get("conversation_stage"),
            "cta_variant": row.get("cta_variant"),
            "cta_shown": 1 if row.get("cta_shown") else 0,
            "lead_magnet_type": row.get("lead_magnet_type"),
            "lead_magnet_delivered": 1 if row.get("lead_magnet_delivered") else 0,
            "notes": row.get("notes"),
            "last_message_at": row.get("last_message_at"),
            "notification_sent": 1 if row.get("notification_sent") else 0,
            "notification_sent_at": row.get("notification_sent_at"),
        }

    # --- операции -----------------------------------------------------------

    def _upsert(self, body: dict) -> dict:
        result = self._post("/api/v1/leads", {"source": SOURCE, **body})
        if not isinstance(result, dict) or result.get("legacy_lead_id") is None:
            if body.get("update_only") and result is None:
                return {}
            raise LeadStoreError(f"core-api did not return a lead number: {result!r}")
        return result

    def _lead_body(self, user_id: int, lead_data: dict) -> dict:
        user = self._local_user_by_id(int(user_id))
        telegram_id = self._telegram_id(user_id)
        body = {"telegram_user_id": telegram_id, **self.payload_from_legacy(lead_data)}
        # Контакт — только когда есть из чего его собрать: пустым не затирать.
        contact = self._contact_for(lead_data or {}, user)
        if contact and (lead_data.get("phone") or lead_data.get("email") or "name" in (lead_data or {})):
            body["contact"] = contact
        return body

    def create_or_update_lead(self, user_id: int, lead_data: dict) -> int:
        row = self._upsert(self._lead_body(user_id, lead_data))
        logger.info("Lead %s upserted for user %s", row["legacy_lead_id"], user_id)
        return int(row["legacy_lead_id"])

    def create_new_lead(self, user_id: int, lead_data: dict) -> int:
        row = self._upsert({"force_new": True, **self._lead_body(user_id, lead_data)})
        logger.info("New lead %s created for user %s", row["legacy_lead_id"], user_id)
        return int(row["legacy_lead_id"])

    def update_lead_by_id(self, lead_id: int, lead_data: dict) -> bool:
        payload = self.payload_from_legacy(lead_data)
        if not payload:
            return False
        row = self._upsert({"legacy_lead_id": int(lead_id), "update_only": True, **payload})
        return bool(row)

    def get_lead_by_user_id(self, user_id: int) -> dict | None:
        user = self._local_user_by_id(int(user_id))
        telegram_id = (user or {}).get("telegram_id")
        if not telegram_id:
            return None
        self._user_ids[int(telegram_id)] = int(user_id)
        rows = self._get(
            "/api/v1/leads", {"source_filter": SOURCE, "telegram_user_id": int(telegram_id), "limit": 1}
        )
        return self.lead_from_core(rows[0]) if isinstance(rows, list) and rows else None

    def get_lead_by_core_id(self, core_lead_id: str) -> dict | None:
        row = self._get(f"/api/v1/leads/{core_lead_id}")
        return self.lead_from_core(row) if isinstance(row, dict) else None

    def record_intake_lead(self, user_id: int, core_lead_id: str | None, lead_data: dict) -> int | None:
        """Номер лида, к которому ядро привязало обращение, с квалификацией бота.

        Обращение заводит или находит лид само; боту остаётся дописать в него
        свои поля (температуру, шаг воронки) и получить номер для аналитики.
        Если ядро не подтвердило обращение, лид заводится обычным путём —
        чтобы человек не пропал, пока обращение будут разбирать вручную.
        """
        if core_lead_id:
            lead = self.get_lead_by_core_id(core_lead_id)
            if lead and lead.get("id"):
                self.update_lead_by_id(int(lead["id"]), lead_data)
                return int(lead["id"])
        return self.create_new_lead(user_id, lead_data)

    def get_lead_by_id(self, lead_id: int) -> dict | None:
        rows = self._get("/api/v1/leads", {"source_filter": SOURCE, "legacy_lead_id": int(lead_id), "limit": 1})
        return self.lead_from_core(rows[0]) if isinstance(rows, list) and rows else None

    def get_all_leads(
        self, temperature: str | None = None, status: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        rows = self._get(
            "/api/v1/leads",
            {
                "source_filter": SOURCE,
                "temperature_filter": temperature or None,
                "status_filter": status or None,
                "limit": max(1, min(int(limit), 500)),
                "offset": max(0, int(offset)),
            },
        )
        return [self.lead_from_core(row) for row in rows] if isinstance(rows, list) else []

    def get_leads_ready_for_notification(self, idle_minutes: int = 5, limit: int = 20) -> list[dict]:
        rows = self._get(
            "/api/v1/leads/notifications/pending",
            {"idle_minutes": int(idle_minutes), "source_filter": SOURCE, "limit": int(limit)},
        )
        if not isinstance(rows, list):
            logger.warning("Core lead notification queue is unavailable; delivery is deferred")
            return []
        return [lead for lead in (self.lead_from_core(row) for row in rows) if lead and lead.get("id")]

    def mark_lead_notification_sent(self, lead_id: int) -> bool:
        lead = self.get_lead_by_id(lead_id)
        if not lead or not lead.get("core_lead_id"):
            return False
        result = self._post(f"/api/v1/leads/{lead['core_lead_id']}/notification-sent", {})
        return result is not None

    def update_lead_last_message_time(self, user_id: int) -> None:
        telegram_id = self._telegram_id(user_id)
        self._upsert(
            {
                "telegram_user_id": telegram_id,
                "update_only": True,
                "last_message_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def update_lead_funnel_state(
        self,
        user_id: int,
        conversation_stage: str | None = None,
        cta_variant: str | None = None,
        cta_shown: bool | None = None,
    ) -> None:
        payload = self.payload_from_legacy(
            {"conversation_stage": conversation_stage, "cta_variant": cta_variant, "cta_shown": cta_shown}
        )
        if not payload:
            return
        self._upsert({"telegram_user_id": self._telegram_id(user_id), "update_only": True, **payload})

    def update_lead_funnel_state_by_id(
        self,
        lead_id: int,
        conversation_stage: str | None = None,
        cta_variant: str | None = None,
        cta_shown: bool | None = None,
    ) -> None:
        self.update_lead_by_id(
            lead_id,
            {"conversation_stage": conversation_stage, "cta_variant": cta_variant, "cta_shown": cta_shown},
        )

    def handover_sequence(self, min_next: int) -> int | None:
        result = self._post("/api/v1/leads/legacy-sequence", {"min_next": int(min_next)})
        return int(result["next_legacy_lead_id"]) if isinstance(result, dict) else None

    def claim_or_create_from_legacy(self, legacy_row: dict, telegram_id: int | None) -> str | None:
        """Перенос старой строки SQLite в ядро — один раз и без затирания.

        Сначала пробуем присвоить номер лиду этого аккаунта, который ядро уже
        завело само (по обращению) и у которого номера нет: содержимое такого
        лида не трогаем — его мог править юрист. Если присваивать некому,
        заводим лид с содержимым старой строки и её датой.
        """
        legacy_id = int(legacy_row["id"])
        if telegram_id:
            claimed = self._post(
                "/api/v1/leads",
                {
                    "source": SOURCE,
                    "legacy_lead_id": legacy_id,
                    "telegram_user_id": int(telegram_id),
                    "claim_unlinked": True,
                    "update_only": True,
                },
            )
            if isinstance(claimed, dict) and claimed.get("id"):
                return str(claimed["id"])
        body = {"source": SOURCE, "legacy_lead_id": legacy_id, **self.payload_from_legacy(legacy_row)}
        if telegram_id:
            body["telegram_user_id"] = int(telegram_id)
        if legacy_row.get("created_at"):
            body["created_at"] = str(legacy_row["created_at"])
        created = self._post("/api/v1/leads", body)
        return str(created["id"]) if isinstance(created, dict) and created.get("id") else None
