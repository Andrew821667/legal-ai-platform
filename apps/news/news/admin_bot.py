from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from news.core_client import CoreClient
from news.logging_config import setup_logging
from news.settings import settings

setup_logging()
logger = logging.getLogger(__name__)


def _parse_admin_ids(raw: str) -> set[int]:
    result: set[int] = set()
    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        try:
            result.add(int(item))
        except ValueError:
            logger.warning("invalid_news_admin_id", extra={"value": item})
    return result


def _is_enabled(value: Any) -> bool:
    return bool(value)


class NewsAdminBot:
    def __init__(self) -> None:
        self.admin_ids = _parse_admin_ids(settings.news_admin_ids)
        self.client = CoreClient(settings.core_api_url, settings.api_key_news)

    def _is_admin(self, update: Update) -> bool:
        user = update.effective_user
        return bool(user and user.id in self.admin_ids)

    async def _ensure_admin(self, update: Update) -> bool:
        if self._is_admin(update):
            return True
        message = "Доступ к админ-панели ограничен."
        if update.callback_query:
            await update.callback_query.answer(message, show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text(message)
        return False

    def _load_controls(self) -> list[dict[str, Any]]:
        response = self.client.list_automation_controls(scope="news")
        response.raise_for_status()
        rows = response.json()
        rows.sort(key=lambda row: row.get("key", ""))
        return rows

    def _controls_text(self, controls: list[dict[str, Any]]) -> str:
        lines = ["Управление автоматизациями news", ""]
        for row in controls:
            key = row.get("key", "")
            enabled = _is_enabled(row.get("enabled", True))
            mark = "🟢" if enabled else "🔴"
            title = row.get("title") or key
            lines.append(f"{mark} {title}")
            lines.append(f"   {key}")
        lines.append("")
        lines.append(f"Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return "\n".join(lines)

    def _controls_keyboard(self, controls: list[dict[str, Any]]) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton("🔄 Обновить", callback_data="refresh"),
                InlineKeyboardButton("📊 Статус очереди", callback_data="status"),
            ],
            [
                InlineKeyboardButton("✅ Включить всё", callback_data="all:1"),
                InlineKeyboardButton("⛔ Отключить всё", callback_data="all:0"),
            ],
        ]
        for row in controls:
            key = str(row.get("key") or "")
            enabled = _is_enabled(row.get("enabled", True))
            next_value = "0" if enabled else "1"
            icon = "🟢" if enabled else "🔴"
            title = str(row.get("title") or key)
            button_text = f"{icon} {title}"
            rows.append([InlineKeyboardButton(button_text[:60], callback_data=f"set:{key}:{next_value}")])
        return InlineKeyboardMarkup(rows)

    async def _queue_text(self) -> str:
        counts: dict[str, int] = {}
        statuses = ("draft", "scheduled", "publishing", "posted", "failed")
        for status in statuses:
            try:
                response = self.client.list_posts(limit=100, status=status, newest_first=True)
                response.raise_for_status()
                counts[status] = len(response.json())
            except Exception as exc:
                logger.warning("queue_status_fetch_failed", extra={"status": status, "error": str(exc)})
                counts[status] = -1

        next_publish = "нет"
        try:
            response = self.client.list_posts(limit=1, status="scheduled", newest_first=False)
            response.raise_for_status()
            rows = response.json()
            if rows:
                next_publish = str(rows[0].get("publish_at") or "нет")
        except Exception as exc:
            logger.warning("next_publish_fetch_failed", extra={"error": str(exc)})

        return (
            "Состояние очереди публикаций\n\n"
            f"draft: {counts['draft']}\n"
            f"scheduled: {counts['scheduled']}\n"
            f"publishing: {counts['publishing']}\n"
            f"posted (посл.100): {counts['posted']}\n"
            f"failed (посл.100): {counts['failed']}\n\n"
            f"Следующая публикация: {next_publish}"
        )

    async def cmd_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            controls = self._load_controls()
            await update.effective_message.reply_text(
                self._controls_text(controls),
                reply_markup=self._controls_keyboard(controls),
            )
        except Exception as exc:
            logger.exception("admin_panel_load_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(f"Ошибка загрузки панели: {exc}")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        text = await self._queue_text()
        await update.effective_message.reply_text(text)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        await update.effective_message.reply_text(
            "Команды админ-бота:\n"
            "/admin — панель автоматизаций\n"
            "/controls — то же\n"
            "/status — статус очереди публикаций\n"
            "/help — помощь"
        )

    async def cb_controls(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        query = update.callback_query
        await query.answer()
        data = query.data or ""

        try:
            if data == "status":
                await query.message.reply_text(await self._queue_text())
                return

            if data.startswith("all:"):
                enabled = data.split(":", maxsplit=1)[1] == "1"
                controls = self._load_controls()
                for row in controls:
                    key = str(row.get("key") or "")
                    if not key:
                        continue
                    self.client.update_automation_control(key, {"enabled": enabled}).raise_for_status()

            elif data.startswith("set:"):
                _, key, value = data.split(":", maxsplit=2)
                enabled = value == "1"
                self.client.update_automation_control(key, {"enabled": enabled}).raise_for_status()

            controls = self._load_controls()
            await query.edit_message_text(
                self._controls_text(controls),
                reply_markup=self._controls_keyboard(controls),
            )
        except Exception as exc:
            logger.exception("admin_callback_failed", extra={"callback_data": data, "error": str(exc)})
            await query.message.reply_text(f"Ошибка операции: {exc}")

    def run(self) -> int:
        if not settings.telegram_bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is required")
            return 1
        if not settings.api_key_news:
            logger.error("API_KEY_NEWS is required")
            return 1
        if not self.admin_ids:
            logger.error("NEWS_ADMIN_IDS is empty; admin bot won't start")
            return 1

        app = Application.builder().token(settings.telegram_bot_token).build()
        app.add_handler(CommandHandler("start", self.cmd_panel))
        app.add_handler(CommandHandler("admin", self.cmd_panel))
        app.add_handler(CommandHandler("controls", self.cmd_panel))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CallbackQueryHandler(self.cb_controls, pattern=r"^(refresh|status|all:[01]|set:[a-z0-9_.-]+:[01])$"))

        logger.info("news_admin_bot_started", extra={"admins": sorted(self.admin_ids)})
        app.run_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)
        return 0


def main() -> int:
    return NewsAdminBot().run()


if __name__ == "__main__":
    raise SystemExit(main())
