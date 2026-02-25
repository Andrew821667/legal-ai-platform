import logging
import csv
import io
import asyncio
from typing import Dict
import database
from config import Config

config = Config()

logger = logging.getLogger(__name__)

class AdminInterface:
    def __init__(self, db):
        self.db = db

    def _get_funnel_payload(self, days=30) -> Dict:
        funnel_data = self.db.get_funnel_report(days)
        ab_data = self.db.get_ab_cta_report(days)
        return {"funnel": funnel_data, "ab": ab_data, "days": days}

    def format_leads_list(self, temperature=None, status=None, limit=20):
        try:
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

            lead = self.db.get_lead_by_id(lead_id) if lead_id else None
            user = self.db.get_user_by_id(lead["user_id"]) if lead else None

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
