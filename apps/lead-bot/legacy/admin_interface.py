import logging
import csv
import io
import asyncio
import json
import urllib.parse
import urllib.request
from typing import Dict
import database
from config import Config

config = Config()

logger = logging.getLogger(__name__)

class AdminInterface:
    def __init__(self, db):
        self.db = db
        self.core_api_url = config.CORE_API_URL.rstrip("/")
        self.core_api_enabled = bool(config.CORE_API_SYNC_ENABLED and self.core_api_url and config.API_KEY_BOT)

    def _core_headers(self) -> dict[str, str]:
        return {"X-API-Key": config.API_KEY_BOT, "Content-Type": "application/json"}

    def _core_get_json(self, path: str, params: dict | None = None):
        if not self.core_api_enabled:
            return None

        query = ""
        if params:
            cleaned = {key: value for key, value in params.items() if value is not None}
            if cleaned:
                query = "?" + urllib.parse.urlencode(cleaned)
        request = urllib.request.Request(
            url=f"{self.core_api_url}{path}{query}",
            headers=self._core_headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=config.CORE_API_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except Exception as error:
            logger.warning("Core API read fallback to SQLite for %s: %s", path, error)
            return None

    def _map_core_lead(self, row: dict) -> dict:
        return {
            "id": row.get("id"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "name": row.get("name"),
            "company": row.get("company") or "",
            "email": row.get("email") or "",
            "phone": row.get("phone") or "",
            "temperature": row.get("temperature") or "cold",
            "status": row.get("status"),
            "service_category": row.get("service_category") or "",
            "specific_need": row.get("specific_need") or "",
            "pain_point": row.get("pain_point") or "",
            "budget": row.get("budget") or "",
            "urgency": row.get("urgency") or "",
            "industry": row.get("industry") or "",
            "conversation_stage": row.get("conversation_stage") or "",
            "cta_variant": row.get("cta_variant") or "",
            "cta_shown": row.get("cta_shown") or False,
            "lead_magnet_type": row.get("lead_magnet_type") or "",
            "lead_magnet_delivered": row.get("lead_magnet_delivered") or False,
        }

    def _map_core_user(self, row: dict) -> dict:
        return {
            "telegram_id": row.get("telegram_id"),
            "username": row.get("username"),
            "first_name": row.get("first_name"),
            "last_name": row.get("last_name"),
            "consent_given": bool(row.get("consent_given")),
            "consent_date": row.get("consent_date"),
            "consent_revoked": bool(row.get("consent_revoked")),
            "consent_revoked_at": row.get("consent_revoked_at"),
            "transborder_consent": bool(row.get("transborder_consent")),
            "transborder_consent_date": row.get("transborder_consent_date"),
            "marketing_consent": bool(row.get("marketing_consent")),
            "marketing_consent_date": row.get("marketing_consent_date"),
            "conversation_stage": row.get("conversation_stage"),
            "cta_variant": row.get("cta_variant"),
            "cta_shown": bool(row.get("cta_shown")),
            "cta_shown_at": row.get("cta_shown_at"),
            "created_at": row.get("created_at"),
            "last_interaction": row.get("last_interaction"),
        }

    def get_user_by_telegram_id(self, telegram_id: int) -> dict | None:
        core_users = self._core_get_json("/api/v1/users", {"telegram_id": telegram_id, "limit": 1})
        core_user = self._map_core_user(core_users[0]) if isinstance(core_users, list) and core_users else None
        local_user = self.db.get_user_by_telegram_id(telegram_id)
        if local_user and core_user:
            merged = dict(local_user)
            merged.update({k: v for k, v in core_user.items() if v is not None})
            return merged
        if local_user:
            return local_user
        return core_user

    def get_recent_users(self, limit: int = 20) -> list[dict]:
        core_users = self._core_get_json("/api/v1/users", {"limit": limit})
        if isinstance(core_users, list):
            return [self._map_core_user(row) for row in core_users]
        return self.db.get_recent_users(limit=limit)

    def get_users_without_consent(self, limit: int = 20) -> list[dict]:
        core_users = self._core_get_json("/api/v1/users", {"without_consent": True, "limit": limit})
        if isinstance(core_users, list):
            return [self._map_core_user(row) for row in core_users]
        return self.db.get_users_without_consent(limit=limit)

    def get_users_with_revoked_consent(self, limit: int = 20) -> list[dict]:
        core_users = self._core_get_json("/api/v1/users", {"revoked_only": True, "limit": limit})
        if isinstance(core_users, list):
            return [self._map_core_user(row) for row in core_users]
        return self.db.get_users_with_revoked_consent(limit=limit)

    def get_latest_lead_for_telegram_user(self, telegram_id: int) -> dict:
        core_leads = self._core_get_json(
            "/api/v1/leads",
            {
                "source_filter": "telegram_bot",
                "telegram_user_id": telegram_id,
                "limit": 1,
            },
        )
        if isinstance(core_leads, list) and core_leads:
            return self._map_core_lead(core_leads[0])

        target_user = self.db.get_user_by_telegram_id(telegram_id)
        if not target_user:
            return {}
        return self.db.get_lead_by_user_id(target_user["id"]) or {}

    def get_lead_snapshot_by_legacy_id(self, legacy_lead_id: int) -> dict:
        core_leads = self._core_get_json(
            "/api/v1/leads",
            {
                "source_filter": "telegram_bot",
                "legacy_lead_id": legacy_lead_id,
                "limit": 1,
            },
        )
        if isinstance(core_leads, list) and core_leads:
            return self._map_core_lead(core_leads[0])
        return self.db.get_lead_by_id(legacy_lead_id) or {}

    def get_user_snapshot(self, telegram_id: int) -> dict | None:
        target_user = self.get_user_by_telegram_id(telegram_id)
        if not target_user:
            return None

        consent = {
            "consent_given": bool(target_user.get("consent_given")),
            "consent_date": target_user.get("consent_date"),
            "consent_revoked": bool(target_user.get("consent_revoked")),
            "consent_revoked_at": target_user.get("consent_revoked_at"),
            "transborder_consent": bool(target_user.get("transborder_consent")),
            "transborder_consent_date": target_user.get("transborder_consent_date"),
            "marketing_consent": bool(target_user.get("marketing_consent")),
            "marketing_consent_date": target_user.get("marketing_consent_date"),
        }
        lead = self.get_latest_lead_for_telegram_user(telegram_id)
        return {
            "user": target_user,
            "lead": lead,
            "consent": consent,
        }

    def export_user_data(self, telegram_id: int) -> dict:
        target_user = self.db.get_user_by_telegram_id(telegram_id)
        if not target_user:
            return {}

        payload = self.db.export_user_data(target_user["id"])
        core_lead = self.get_latest_lead_for_telegram_user(telegram_id)
        if core_lead:
            payload["lead"] = core_lead
        return payload

    def _get_funnel_payload(self, days=30) -> Dict:
        funnel_data = self.db.get_funnel_report(days)
        ab_data = self.db.get_ab_cta_report(days)
        return {"funnel": funnel_data, "ab": ab_data, "days": days}

    def format_leads_list(self, temperature=None, status=None, limit=20):
        try:
            leads = None
            core_leads = self._core_get_json(
                "/api/v1/leads",
                {
                    "status_filter": status,
                    "source_filter": "telegram_bot",
                    "temperature_filter": temperature,
                    "limit": limit,
                },
            )
            if isinstance(core_leads, list):
                leads = [self._map_core_lead(row) for row in core_leads]
            if leads is None:
                leads = self.db.get_all_leads(temperature, status, limit)
            if not leads:
                return "📋 СПИСОК ЛИДОВ\n\nЛидов не найдено"
            
            message = f"📋 СПИСОК ЛИДОВ ({len(leads)})\n\n"
            for i, lead in enumerate(leads, 1):
                # lead - это dict, получаем значения безопасно
                name = lead.get('name', 'N/A') or lead.get('full_name', 'N/A')
                company = lead.get('company', '')
                temp = lead.get('temperature', 'unknown')
                emoji = {'hot': '🔥', 'warm': '♨️', 'cold': '❄️'}.get(temp, '❓')
                message += f"{i}. {emoji} {name} ({company})\n"
            return message
        except Exception as e:
            logger.error(f"Error in format_leads_list: {e}", exc_info=True)
            return f"❌ Ошибка: {e}"
    
    def format_statistics(self, days=30):
        try:
            stats = self.db.get_statistics(days)
            core_summary = self._core_get_json("/api/v1/leads/stats/summary")
            if isinstance(core_summary, dict):
                stats = dict(stats)
                stats["total_leads"] = core_summary.get("total_leads", stats.get("total_leads", 0))
                stats["cold_leads"] = core_summary.get("cold_leads", stats.get("cold_leads", 0))
                stats["warm_leads"] = core_summary.get("warm_leads", stats.get("warm_leads", 0))
                stats["hot_leads"] = core_summary.get("hot_leads", stats.get("hot_leads", 0))
                stats["stage_discover"] = core_summary.get("stage_discover", stats.get("stage_discover", 0))
                stats["stage_diagnose"] = core_summary.get("stage_diagnose", stats.get("stage_diagnose", 0))
                stats["stage_qualify"] = core_summary.get("stage_qualify", stats.get("stage_qualify", 0))
                stats["stage_propose"] = core_summary.get("stage_propose", stats.get("stage_propose", 0))
                stats["stage_handoff"] = core_summary.get("stage_handoff", stats.get("stage_handoff", 0))
            message = (
                f"📊 СТАТИСТИКА\n\n"
                f"👥 Пользователей: {stats.get('total_users', 0)}\n"
                f"💬 Сообщений: {stats.get('total_messages', 0)}\n"
                f"📋 Лидов: {stats.get('total_leads', 0)}\n"
                f"  🔥 Горячих: {stats.get('hot_leads', 0)}\n"
                f"  ♨️ Теплых: {stats.get('warm_leads', 0)}\n"
                f"  ❄️ Холодных: {stats.get('cold_leads', 0)}\n\n"
                f"📈 Этапы воронки (текущий срез):\n"
                f"• Discover: {stats.get('stage_discover', 0)}\n"
                f"• Diagnose: {stats.get('stage_diagnose', 0)}\n"
                f"• Qualify: {stats.get('stage_qualify', 0)}\n"
                f"• Propose: {stats.get('stage_propose', 0)}\n"
                f"• Handoff: {stats.get('stage_handoff', 0)}"
            )
            return message
        except Exception as e:
            logger.error(f"Error: {e}")
            return f"❌ Ошибка: {e}"

    def format_funnel_report(self, days=30):
        """Подробный отчет: воронка + A/B CTA."""
        try:
            payload = self._get_funnel_payload(days)
            funnel_data = payload["funnel"]
            ab_data = payload["ab"]

            stage = funnel_data.get("stage_counts", {})
            events = funnel_data.get("event_counts", {})
            rates = funnel_data.get("transitions", {})
            variants = ab_data.get("variants", {})
            total = ab_data.get("total", {})

            def _line_rate(name: str, key: str) -> str:
                return f"• {name}: {rates.get(key, 0.0)}%"

            a = variants.get("A", {})
            b = variants.get("B", {})

            message = (
                f"📈 ВОРОНКА И A/B ОТЧЕТ (за {days} дн.)\n\n"
                f"1) Этапы (уникальные пользователи):\n"
                f"• Discover: {stage.get('discover', 0)}\n"
                f"• Diagnose: {stage.get('diagnose', 0)}\n"
                f"• Qualify: {stage.get('qualify', 0)}\n"
                f"• Propose: {stage.get('propose', 0)}\n"
                f"• Handoff: {stage.get('handoff', 0)}\n\n"
                f"2) Конверсии по этапам:\n"
                f"{_line_rate('Discover → Diagnose', 'discover_to_diagnose')}\n"
                f"{_line_rate('Diagnose → Qualify', 'diagnose_to_qualify')}\n"
                f"{_line_rate('Qualify → Propose', 'qualify_to_propose')}\n"
                f"{_line_rate('Propose → Handoff', 'propose_to_handoff')}\n\n"
                f"3) CTA воронка:\n"
                f"• CTA shown (users): {events.get('cta_shown_users', 0)}\n"
                f"• CTA clicked (users): {events.get('cta_clicked_users', 0)}\n"
                f"• Handoff done (users): {events.get('handoff_users', 0)}\n"
                f"{_line_rate('CTR (click/shown)', 'cta_click_from_shown')}\n"
                f"{_line_rate('Handoff/shown', 'handoff_from_shown')}\n\n"
                f"4) A/B сравнение CTA:\n"
                f"• Variant A: shown={a.get('shown_users', 0)}, "
                f"clicked={a.get('clicked_users', 0)}, handoff={a.get('handoff_users', 0)}, "
                f"CTR={a.get('click_rate', 0.0)}%, Handoff={a.get('handoff_rate', 0.0)}%\n"
                f"• Variant B: shown={b.get('shown_users', 0)}, "
                f"clicked={b.get('clicked_users', 0)}, handoff={b.get('handoff_users', 0)}, "
                f"CTR={b.get('click_rate', 0.0)}%, Handoff={b.get('handoff_rate', 0.0)}%\n\n"
                f"Итого: shown={total.get('shown_users', 0)}, "
                f"clicked={total.get('clicked_users', 0)}, handoff={total.get('handoff_users', 0)}, "
                f"CTR={total.get('click_rate', 0.0)}%, Handoff={total.get('handoff_rate', 0.0)}%"
            )
            return message
        except Exception as e:
            logger.error(f"Error in format_funnel_report: {e}", exc_info=True)
            return f"❌ Ошибка отчета воронки: {e}"

    def export_funnel_report_csv(self, days=30) -> str:
        """Экспорт воронки и A/B в CSV."""
        payload = self._get_funnel_payload(days)
        funnel_data = payload["funnel"]
        ab_data = payload["ab"]

        stage = funnel_data.get("stage_counts", {})
        events = funnel_data.get("event_counts", {})
        transitions = funnel_data.get("transitions", {})
        variants = ab_data.get("variants", {})
        total = ab_data.get("total", {})

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["section", "metric", "value"])
        writer.writerow(["meta", "window_days", days])

        for key in ("discover", "diagnose", "qualify", "propose", "handoff"):
            writer.writerow(["stage_counts", key, stage.get(key, 0)])

        for key in ("cta_shown_users", "cta_clicked_users", "handoff_users"):
            writer.writerow(["event_counts", key, events.get(key, 0)])

        for key in (
            "discover_to_diagnose",
            "diagnose_to_qualify",
            "qualify_to_propose",
            "propose_to_handoff",
            "cta_click_from_shown",
            "handoff_from_shown",
        ):
            writer.writerow(["transitions_pct", key, transitions.get(key, 0.0)])

        for variant in ("A", "B"):
            data = variants.get(variant, {})
            writer.writerow([f"ab_variant_{variant}", "shown_users", data.get("shown_users", 0)])
            writer.writerow([f"ab_variant_{variant}", "clicked_users", data.get("clicked_users", 0)])
            writer.writerow([f"ab_variant_{variant}", "handoff_users", data.get("handoff_users", 0)])
            writer.writerow([f"ab_variant_{variant}", "click_rate_pct", data.get("click_rate", 0.0)])
            writer.writerow([f"ab_variant_{variant}", "handoff_rate_pct", data.get("handoff_rate", 0.0)])

        writer.writerow(["ab_total", "shown_users", total.get("shown_users", 0)])
        writer.writerow(["ab_total", "clicked_users", total.get("clicked_users", 0)])
        writer.writerow(["ab_total", "handoff_users", total.get("handoff_users", 0)])
        writer.writerow(["ab_total", "click_rate_pct", total.get("click_rate", 0.0)])
        writer.writerow(["ab_total", "handoff_rate_pct", total.get("handoff_rate", 0.0)])

        return out.getvalue()

    def export_funnel_report_markdown(self, days=30) -> str:
        """Экспорт воронки и A/B в Markdown."""
        payload = self._get_funnel_payload(days)
        funnel_data = payload["funnel"]
        ab_data = payload["ab"]

        stage = funnel_data.get("stage_counts", {})
        events = funnel_data.get("event_counts", {})
        rates = funnel_data.get("transitions", {})
        variants = ab_data.get("variants", {})
        total = ab_data.get("total", {})

        a = variants.get("A", {})
        b = variants.get("B", {})

        return (
            f"# Funnel and A/B Report ({days} days)\n\n"
            "## Stage counts\n"
            "| Stage | Users |\n"
            "|---|---:|\n"
            f"| Discover | {stage.get('discover', 0)} |\n"
            f"| Diagnose | {stage.get('diagnose', 0)} |\n"
            f"| Qualify | {stage.get('qualify', 0)} |\n"
            f"| Propose | {stage.get('propose', 0)} |\n"
            f"| Handoff | {stage.get('handoff', 0)} |\n\n"
            "## Stage transitions\n"
            "| Transition | Conversion |\n"
            "|---|---:|\n"
            f"| Discover -> Diagnose | {rates.get('discover_to_diagnose', 0.0)}% |\n"
            f"| Diagnose -> Qualify | {rates.get('diagnose_to_qualify', 0.0)}% |\n"
            f"| Qualify -> Propose | {rates.get('qualify_to_propose', 0.0)}% |\n"
            f"| Propose -> Handoff | {rates.get('propose_to_handoff', 0.0)}% |\n\n"
            "## CTA funnel\n"
            "| Metric | Value |\n"
            "|---|---:|\n"
            f"| CTA shown users | {events.get('cta_shown_users', 0)} |\n"
            f"| CTA clicked users | {events.get('cta_clicked_users', 0)} |\n"
            f"| Handoff users | {events.get('handoff_users', 0)} |\n"
            f"| CTR (click/shown) | {rates.get('cta_click_from_shown', 0.0)}% |\n"
            f"| Handoff from shown | {rates.get('handoff_from_shown', 0.0)}% |\n\n"
            "## A/B CTA\n"
            "| Variant | Shown | Clicked | Handoff | CTR | Handoff rate |\n"
            "|---|---:|---:|---:|---:|---:|\n"
            f"| A | {a.get('shown_users', 0)} | {a.get('clicked_users', 0)} | {a.get('handoff_users', 0)} | {a.get('click_rate', 0.0)}% | {a.get('handoff_rate', 0.0)}% |\n"
            f"| B | {b.get('shown_users', 0)} | {b.get('clicked_users', 0)} | {b.get('handoff_users', 0)} | {b.get('click_rate', 0.0)}% | {b.get('handoff_rate', 0.0)}% |\n"
            f"| Total | {total.get('shown_users', 0)} | {total.get('clicked_users', 0)} | {total.get('handoff_users', 0)} | {total.get('click_rate', 0.0)}% | {total.get('handoff_rate', 0.0)}% |\n"
        )
    
    def export_leads_to_csv(self):
        try:
            leads = None
            core_leads = self._core_get_json(
                "/api/v1/leads",
                {"source_filter": "telegram_bot", "limit": 500},
            )
            if isinstance(core_leads, list):
                leads = [self._map_core_lead(row) for row in core_leads]
            if leads is None:
                leads = self.db.get_all_leads(limit=10000)
            if not leads:
                return ""

            out = io.StringIO()
            writer = csv.writer(out)
            writer.writerow([
                "id",
                "created_at",
                "updated_at",
                "temperature",
                "status",
                "name",
                "company",
                "email",
                "phone",
                "service_category",
                "specific_need",
                "pain_point",
                "budget",
                "urgency",
                "industry",
                "conversation_stage",
                "cta_variant",
                "cta_shown",
                "lead_magnet_type",
                "lead_magnet_delivered",
            ])

            for lead in leads:
                writer.writerow([
                    lead.get("id"),
                    lead.get("created_at"),
                    lead.get("updated_at"),
                    lead.get("temperature"),
                    lead.get("status"),
                    lead.get("name"),
                    lead.get("company"),
                    lead.get("email"),
                    lead.get("phone"),
                    lead.get("service_category"),
                    lead.get("specific_need"),
                    lead.get("pain_point"),
                    lead.get("budget"),
                    lead.get("urgency"),
                    lead.get("industry"),
                    lead.get("conversation_stage"),
                    lead.get("cta_variant"),
                    lead.get("cta_shown"),
                    lead.get("lead_magnet_type"),
                    lead.get("lead_magnet_delivered"),
                ])

            return out.getvalue()
        except Exception as e:
            logger.error(f"Error in export_leads_to_csv: {e}", exc_info=True)
            return ""
    
    def get_conversation_history_text(self, telegram_id):
        try:
            user = self.db.get_user_by_telegram_id(telegram_id)
            if not user:
                return f"📝 История диалога\n\nПользователь с telegram_id={telegram_id} не найден."

            history = self.db.get_conversation_history(user["id"], limit=100)
            if not history:
                return f"📝 История диалога ({telegram_id})\n\nДиалогов пока нет."

            lines = [f"📝 История диалога ({telegram_id})", ""]
            for item in history:
                role = "👤 Клиент" if item.get("role") == "user" else "🤖 Бот"
                ts = item.get("timestamp", "")
                text = item.get("message") or item.get("content") or ""
                lines.append(f"{role} [{ts}]:")
                lines.append(text)
                lines.append("")

            return "\n".join(lines).strip()
        except Exception as e:
            logger.error(f"Error in get_conversation_history_text: {e}", exc_info=True)
            return f"❌ Ошибка при получении истории: {e}"
    
    def send_admin_notification(self, bot, lead_id, notification_type, message=None):
        """
        Отправка уведомления админу.
        Метод синхронный, но отправку в Telegram запускает как async-задачу.
        """
        try:
            if lead_id:
                self.db.create_notification(lead_id, notification_type, message or "")

            legacy_lead = self.db.get_lead_by_id(lead_id) if lead_id else None
            lead = self.get_lead_snapshot_by_legacy_id(lead_id) if lead_id else None
            user = self.db.get_user_by_id(legacy_lead["user_id"]) if legacy_lead and legacy_lead.get("user_id") else None

            type_header = {
                "handoff_request": "📞 Запрос на связь с командой",
                "lead_magnet_requested": "🎁 Запрошен лид-магнит",
                "new_lead": "🆕 Новый лид",
            }.get(notification_type, "🔔 Событие по лиду")

            lead_name = (lead or {}).get("name") or (user or {}).get("first_name") or "Не указано"
            company = (lead or {}).get("company") or "Не указана"
            email = (lead or {}).get("email") or "Не указан"
            phone = (lead or {}).get("phone") or "Не указан"
            temp = (lead or {}).get("temperature") or "unknown"

            text = (
                f"{type_header}\n\n"
                f"Lead ID: {lead_id or 'n/a'}\n"
                f"Имя: {lead_name}\n"
                f"Компания: {company}\n"
                f"Email: {email}\n"
                f"Телефон: {phone}\n"
                f"Температура: {temp}\n\n"
                f"Детали: {message or '—'}"
            )

            if bot is None:
                logger.warning("send_admin_notification skipped: bot is None")
                return

            target_chat_id = config.LEADS_CHAT_ID if config.LEADS_CHAT_ID else config.ADMIN_TELEGRAM_ID
            send_coro = bot.send_message(chat_id=target_chat_id, text=text)

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(send_coro)
            except RuntimeError:
                asyncio.run(send_coro)

        except Exception as e:
            logger.error(f"Error in send_admin_notification: {e}", exc_info=True)

# Инициализируем глобальный объект
try:
    _db = database.db
    admin_interface = AdminInterface(_db)
except Exception as e:
    print(f"Warning: Could not initialize admin_interface: {e}")
    admin_interface = None
