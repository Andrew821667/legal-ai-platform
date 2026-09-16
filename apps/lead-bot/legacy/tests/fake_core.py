"""Ядро в памяти — для тестов лидов бота.

Повторяет правила upsert'а из core_api/routers/leads.py ровно настолько,
чтобы бот можно было проверить без PostgreSQL: подбор по номеру, по
аккаунту (последний лид), force_new / update_only / claim_unlinked, номер
из счётчика, очередь уведомлений. Это не второй экземпляр ядра — если
правила там меняются, меняются и здесь.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from core_leads import LeadStoreError

_FLAGS = ("force_new", "update_only", "claim_unlinked", "created_at")


class FakeCore:
    def __init__(self) -> None:
        self.leads: list[dict] = []
        self.next_legacy_id = 1
        self.calls: list[tuple[str, str, dict | None]] = []
        self.down = False
        self.notified: list[str] = []

    # --- служебное ---------------------------------------------------------

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_lead(self, body: dict) -> dict:
        row = {
            "id": str(uuid.uuid4()),
            "created_at": body.get("created_at") or self._now(),
            "updated_at": self._now(),
            "source": body.get("source", "telegram_bot"),
            "legacy_lead_id": body.get("legacy_lead_id"),
            "telegram_user_id": body.get("telegram_user_id"),
            "status": "new",
            "cta_shown": False,
            "lead_magnet_delivered": False,
            "notification_sent": False,
            "notification_sent_at": None,
            "last_message_at": None,
        }
        for key in (
            "name", "contact", "company", "email", "phone", "temperature", "service_category",
            "specific_need", "pain_point", "budget", "urgency", "industry", "conversation_stage",
            "cta_variant", "lead_magnet_type", "notes", "team_size", "contracts_per_month",
        ):
            row.setdefault(key, None)
        if row["legacy_lead_id"] is None and row["source"] == "telegram_bot":
            row["legacy_lead_id"] = self.next_legacy_id
            self.next_legacy_id += 1
        self._apply(row, body)
        return row

    def _apply(self, row: dict, body: dict) -> None:
        for key, value in body.items():
            if key in _FLAGS or value is None:
                continue
            row[key] = value
        row["updated_at"] = self._now()

    def _by_legacy(self, legacy_id: int) -> dict | None:
        return next((row for row in self.leads if row["legacy_lead_id"] == legacy_id), None)

    def lead_of(self, telegram_user_id: int) -> dict | None:
        rows = [row for row in self.leads if row["telegram_user_id"] == telegram_user_id]
        return sorted(rows, key=lambda row: row["created_at"])[-1] if rows else None

    # --- транспорт ---------------------------------------------------------

    def get(self, path: str, params: dict | None = None):
        self.calls.append(("GET", path, params))
        if self.down:
            raise LeadStoreError("core-api unreachable")
        params = {key: value for key, value in (params or {}).items() if value is not None}
        if path == "/api/v1/leads":
            rows = [row for row in self.leads if row["source"] == params.get("source_filter", row["source"])]
            if "telegram_user_id" in params:
                rows = [row for row in rows if row["telegram_user_id"] == int(params["telegram_user_id"])]
            if "legacy_lead_id" in params:
                rows = [row for row in rows if row["legacy_lead_id"] == int(params["legacy_lead_id"])]
            if "status_filter" in params:
                rows = [row for row in rows if row["status"] == params["status_filter"]]
            if "temperature_filter" in params:
                rows = [row for row in rows if row["temperature"] == params["temperature_filter"]]
            rows = sorted(rows, key=lambda row: row["created_at"], reverse=True)
            offset = int(params.get("offset", 0))
            return [dict(row) for row in rows[offset : offset + int(params.get("limit", 100))]]
        if path == "/api/v1/leads/notifications/pending":
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=int(params.get("idle_minutes", 5)))
            rows = [
                row
                for row in self.leads
                if row["last_message_at"]
                and datetime.fromisoformat(row["last_message_at"]) <= cutoff
                and not row["notification_sent"]
                and (
                    row["temperature"] in ("warm", "hot")
                    or (row["name"] and (row["email"] or row["phone"] or row["contact"]) and row["pain_point"])
                )
            ]
            return [dict(row) for row in rows[: int(params.get("limit", 20))]]
        if path.startswith("/api/v1/leads/"):
            core_id = path.rsplit("/", 1)[1]
            row = next((row for row in self.leads if row["id"] == core_id), None)
            return dict(row) if row else None
        return None

    def post(self, path: str, body: dict, idempotency_key: str | None = None):
        self.calls.append(("POST", path, body))
        if self.down:
            raise LeadStoreError("core-api unreachable")
        if path == "/api/v1/leads":
            return self._upsert(body)
        if path == "/api/v1/leads/legacy-sequence":
            self.next_legacy_id = max(self.next_legacy_id, int(body["min_next"]))
            return {"next_legacy_lead_id": self.next_legacy_id}
        if path.endswith("/notification-sent"):
            core_id = path.split("/")[-2]
            row = next((row for row in self.leads if row["id"] == core_id), None)
            if row is None:
                return None
            row["notification_sent"] = True
            row["notification_sent_at"] = self._now()
            self.notified.append(core_id)
            return dict(row)
        return None

    def _upsert(self, body: dict) -> dict | None:
        lead = None
        if body.get("legacy_lead_id") is not None:
            lead = self._by_legacy(int(body["legacy_lead_id"]))
            if lead is None and body.get("claim_unlinked") and body.get("telegram_user_id") is not None:
                lead = next(
                    (
                        row
                        for row in sorted(self.leads, key=lambda row: row["created_at"])
                        if row["telegram_user_id"] == int(body["telegram_user_id"]) and row["legacy_lead_id"] is None
                    ),
                    None,
                )
        elif body.get("force_new"):
            lead = None
        elif body.get("telegram_user_id") is not None:
            lead = self.lead_of(int(body["telegram_user_id"]))
        elif body.get("contact"):
            lead = next((row for row in self.leads if row["contact"] == body["contact"]), None)
        if lead is None and body.get("update_only"):
            return None
        if lead is None:
            lead = self._new_lead(body)
            self.leads.append(lead)
        self._apply(lead, body)
        return dict(lead)


def install(monkeypatch, db, core: FakeCore | None = None) -> FakeCore:
    """Подменяет транспорт хранилища лидов на память."""
    core = core or FakeCore()
    db.leads.use_transport(core)
    return core
