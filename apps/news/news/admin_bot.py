from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from news.core_client import CoreClient
from news.logging_config import setup_logging
from news.settings import settings

setup_logging()
logger = logging.getLogger(__name__)


_POSTS_PAGE_SIZE = 8
_STATE_PENDING_EDIT = "pending_edit"
_STATE_DRAFT_EDIT = "draft_edit"
_STATE_PENDING_PUBLISH_REASON = "pending_publish_reason"
_STATE_DRAFT_PUBLISH = "draft_publish"
_STATE_PENDING_BATCH_PUBLISH_REASON = "pending_batch_publish_reason"
_STATE_DRAFT_BATCH_PUBLISH = "draft_batch_publish"
_POST_LIST_STATUSES = ("draft", "scheduled", "failed")
_MANUAL_QUEUE_FILTERS = ("due", "all")
_BATCH_PUBLISH_MODES = ("page", "top3", "top5")


def _status_label(status: str) -> str:
    mapping = {
        "draft": "🆕 Сгенерированные",
        "scheduled": "✅ Готовые к публикации",
        "failed": "❌ Ошибки публикации",
    }
    return mapping.get(status, status)


def _status_badge(status: str) -> str:
    mapping = {
        "draft": "🆕",
        "scheduled": "✅",
        "failed": "❌",
        "publishing": "⏳",
        "posted": "📤",
    }
    return mapping.get(status, "•")


def _parse_post_list_callback(data: str) -> tuple[str, int]:
    # Новый формат: pl:<status>:<offset>, legacy: pl:<offset>
    parts = data.split(":")
    if len(parts) == 2:
        return "scheduled", int(parts[1])
    if len(parts) >= 3:
        return parts[1], int(parts[2])
    return "scheduled", 0


def _parse_manual_queue_callback(data: str) -> tuple[str, int]:
    # Формат: mq:<filter>:<offset>, legacy: mq:<offset>
    parts = data.split(":")
    if len(parts) == 2:
        return "due", int(parts[1])
    if len(parts) >= 3:
        queue_filter = parts[1]
        if queue_filter not in _MANUAL_QUEUE_FILTERS:
            queue_filter = "due"
        return queue_filter, int(parts[2])
    return "due", 0


def _parse_batch_publish_callback(data: str) -> tuple[str, int, str]:
    # Формат: mbp|mbc|mbn:<filter>:<offset>[:mode]
    parts = data.split(":")
    queue_filter = "due"
    offset = 0
    mode = "page"
    if len(parts) >= 2 and parts[1] in _MANUAL_QUEUE_FILTERS:
        queue_filter = parts[1]
    if len(parts) >= 3:
        offset = int(parts[2])
    if len(parts) >= 4 and parts[3] in _BATCH_PUBLISH_MODES:
        mode = parts[3]
    return queue_filter, offset, mode


def _batch_mode_limit(mode: str) -> int | None:
    if mode == "top3":
        return 3
    if mode == "top5":
        return 5
    return None


def _batch_mode_label(mode: str) -> str:
    mapping = {
        "page": "вся страница",
        "top3": "топ-3",
        "top5": "топ-5",
    }
    return mapping.get(mode, mode)


def _is_batch_mode_allowed(queue_filter: str, mode: str) -> bool:
    if mode in ("top3", "top5") and queue_filter != "due":
        return False
    return True


def _compute_quick_publish_at(slot: str) -> datetime:
    tz = ZoneInfo(settings.tz_name)
    now_local = datetime.now(tz)

    if slot == "h1":
        target_local = now_local + timedelta(hours=1)
    elif slot == "e19":
        target_local = now_local.replace(hour=19, minute=0, second=0, microsecond=0)
        if target_local <= now_local:
            target_local = target_local + timedelta(days=1)
    elif slot == "t10":
        target_local = (now_local + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"Unsupported schedule slot: {slot}")

    return target_local.astimezone(timezone.utc)


def _slot_label(slot: str) -> str:
    mapping = {"h1": "+1ч", "e19": "сегодня/след. 19:00", "t10": "завтра 10:00"}
    return mapping.get(slot, slot)


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


def _split_text_for_telegram(text: str, limit: int = 4000) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    if len(normalized) <= limit:
        return [normalized]

    parts: list[str] = []
    rest = normalized
    while rest:
        if len(rest) <= limit:
            parts.append(rest)
            break
        cut = rest.rfind("\n", 0, limit)
        if cut < int(limit * 0.5):
            cut = rest.rfind(" ", 0, limit)
        if cut < int(limit * 0.5):
            cut = limit
        parts.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    return [part for part in parts if part]


def _queue_context_from_filter(queue_filter: str) -> str:
    return "mq_all" if queue_filter == "all" else "mq_due"


def _queue_filter_from_context(context: str) -> str:
    return "all" if context == "mq_all" else "due"


def _is_manual_queue_context(context: str) -> bool:
    return context.startswith("mq_")


def _normalize_operator_note(note: str, limit: int = 500) -> str:
    normalized = " ".join((note or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


class NewsAdminBot:
    def __init__(self) -> None:
        self.admin_ids = _parse_admin_ids(settings.news_admin_ids)
        self.client = CoreClient(settings.core_api_url, settings.api_key_news)
        self._openai_client: Any | None = None
        self._use_max_tokens_param = "deepseek" in (settings.openai_base_url or "").lower()

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
                InlineKeyboardButton("🆕 Сгенерированные", callback_data="pl:draft:0"),
                InlineKeyboardButton("✅ Готовые", callback_data="pl:scheduled:0"),
            ],
            [InlineKeyboardButton("🚀 Ручная очередь", callback_data="mq:due:0")],
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

    def _load_posts(self, status: str, offset: int) -> tuple[int, list[dict[str, Any]]]:
        response = self.client.list_posts(limit=100, status=status, newest_first=False)
        response.raise_for_status()
        all_rows = response.json()
        total = len(all_rows)
        return total, all_rows[offset : offset + _POSTS_PAGE_SIZE]

    @staticmethod
    def _publish_at_utc(row: dict[str, Any]) -> datetime | None:
        raw_value = row.get("publish_at")
        if raw_value is None:
            return None
        if isinstance(raw_value, datetime):
            parsed = raw_value
        else:
            text = str(raw_value).strip()
            if not text:
                return None
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _load_manual_queue(self, queue_filter: str, offset: int) -> tuple[int, list[dict[str, Any]], int, int]:
        response = self.client.list_posts(limit=100, status="scheduled", newest_first=False)
        response.raise_for_status()
        all_rows = response.json()
        now_utc = datetime.now(timezone.utc)
        due_rows = [row for row in all_rows if (publish_at := self._publish_at_utc(row)) and publish_at <= now_utc]
        filtered_rows = due_rows if queue_filter == "due" else all_rows
        total = len(filtered_rows)
        return total, filtered_rows[offset : offset + _POSTS_PAGE_SIZE], len(due_rows), len(all_rows)

    def _get_post(self, post_id: str) -> dict[str, Any]:
        response = self.client.get_post(post_id)
        response.raise_for_status()
        return response.json()

    def _posts_text(self, total: int, rows: list[dict[str, Any]], offset: int, status: str) -> str:
        label = _status_label(status)
        if not rows:
            return f"{label} (status={status})\n\nСейчас записей нет."

        lines = [f"{label}: {total}", ""]
        for idx, row in enumerate(rows, start=offset + 1):
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            publish_at = str(row.get("publish_at") or "")
            status_badge = _status_badge(str(row.get("status") or status))
            lines.append(f"{idx}. {status_badge} {title[:86]}")
            lines.append(f"   ⏰ {publish_at}")
        return "\n".join(lines)

    def _manual_queue_text(
        self,
        total: int,
        rows: list[dict[str, Any]],
        offset: int,
        queue_filter: str,
        due_total: int,
        scheduled_total: int,
    ) -> str:
        filter_label = "к публикации сейчас" if queue_filter == "due" else "все готовые"
        if not rows:
            return (
                "Ручная очередь публикации\n\n"
                f"Фильтр: {filter_label}\n"
                f"Готовые сейчас: {due_total} из {scheduled_total}\n\n"
                "Сейчас записей нет."
            )

        now_utc = datetime.now(timezone.utc)
        lines = [
            "Ручная очередь публикации",
            f"Фильтр: {filter_label}",
            f"Готовые сейчас: {due_total} из {scheduled_total}",
            "Режимы топ-3/топ-5 доступны только в фильтре «К публикации сейчас».",
            "",
        ]
        for idx, row in enumerate(rows, start=offset + 1):
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            publish_at = str(row.get("publish_at") or "")
            publish_at_utc = self._publish_at_utc(row)
            due_mark = "⚡" if publish_at_utc and publish_at_utc <= now_utc else "🕒"
            lines.append(f"{idx}. {due_mark} {title[:84]}")
            lines.append(f"   ⏰ {publish_at}")
        return "\n".join(lines)

    def _posts_keyboard(self, total: int, rows: list[dict[str, Any]], offset: int, status: str) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        buttons.append(
            [
                InlineKeyboardButton("🆕 Сгенерированные", callback_data="pl:draft:0"),
                InlineKeyboardButton("✅ Готовые", callback_data="pl:scheduled:0"),
            ]
        )
        buttons.append([InlineKeyboardButton("❌ Ошибки", callback_data="pl:failed:0")])
        buttons.append([InlineKeyboardButton("🚀 Ручная очередь", callback_data="mq:due:0")])

        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            status_badge = _status_badge(str(row.get("status") or status))
            buttons.append([InlineKeyboardButton(f"{idx}. {status_badge} {title[:45]}", callback_data=f"pv:{post_id}:{status}:{offset}")])

        if rows and status in ("draft", "failed"):
            buttons.append([InlineKeyboardButton("✅ В готовые (все на странице)", callback_data=f"ba:ready:{status}:{offset}")])

        nav: list[InlineKeyboardButton] = []
        prev_offset = max(0, offset - _POSTS_PAGE_SIZE)
        next_offset = offset + _POSTS_PAGE_SIZE
        if offset > 0:
            nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"pl:{status}:{prev_offset}"))
        if next_offset < total:
            nav.append(InlineKeyboardButton("➡️ Далее", callback_data=f"pl:{status}:{next_offset}"))
        if nav:
            buttons.append(nav)

        buttons.append([InlineKeyboardButton("🔄 Обновить список", callback_data=f"pl:{status}:{offset}")])
        buttons.append([InlineKeyboardButton("◀️ В админ-панель", callback_data="refresh")])
        return InlineKeyboardMarkup(buttons)

    def _manual_queue_keyboard(
        self,
        total: int,
        rows: list[dict[str, Any]],
        offset: int,
        queue_filter: str,
    ) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton("⚡ К публикации сейчас", callback_data="mq:due:0"),
                InlineKeyboardButton("📚 Все готовые", callback_data="mq:all:0"),
            ]
        ]
        context = _queue_context_from_filter(queue_filter)
        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            buttons.append([InlineKeyboardButton(f"{idx}. {title[:45]}", callback_data=f"pv:{post_id}:{context}:{offset}")])

        if rows:
            if queue_filter == "due":
                buttons.append(
                    [
                        InlineKeyboardButton("🚀 Страница", callback_data=f"mbp:{queue_filter}:{offset}:page"),
                        InlineKeyboardButton("⚡ Топ-3", callback_data=f"mbp:{queue_filter}:{offset}:top3"),
                        InlineKeyboardButton("🔥 Топ-5", callback_data=f"mbp:{queue_filter}:{offset}:top5"),
                    ]
                )
            else:
                buttons.append([InlineKeyboardButton("🚀 Опубликовать страницу", callback_data=f"mbp:{queue_filter}:{offset}:page")])

        nav: list[InlineKeyboardButton] = []
        prev_offset = max(0, offset - _POSTS_PAGE_SIZE)
        next_offset = offset + _POSTS_PAGE_SIZE
        if offset > 0:
            nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"mq:{queue_filter}:{prev_offset}"))
        if next_offset < total:
            nav.append(InlineKeyboardButton("➡️ Далее", callback_data=f"mq:{queue_filter}:{next_offset}"))
        if nav:
            buttons.append(nav)

        buttons.append([InlineKeyboardButton("🔄 Обновить очередь", callback_data=f"mq:{queue_filter}:{offset}")])
        buttons.append([InlineKeyboardButton("◀️ В админ-панель", callback_data="refresh")])
        return InlineKeyboardMarkup(buttons)

    def _post_card_text(self, post: dict[str, Any]) -> str:
        title = str(post.get("title") or "Без заголовка")
        publish_at = str(post.get("publish_at") or "")
        status = str(post.get("status") or "")
        text = str(post.get("text") or "")
        preview = text if len(text) <= 2500 else text[:2500] + "\n\n…"
        source_url = str(post.get("source_url") or "")

        parts = [
            f"Пост: {title}",
            f"ID: {post.get('id')}",
            f"Статус: {status}",
            f"Публикация (план): {publish_at}",
            "",
            preview,
        ]
        if source_url:
            parts.extend(["", f"Источник: {source_url}"])
        return "\n".join(parts)

    def _post_card_keyboard(self, post_id: str, status: str, offset: int) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton("⏱ +1ч", callback_data=f"pt:{post_id}:{status}:{offset}:h1"),
                InlineKeyboardButton("🌙 19:00", callback_data=f"pt:{post_id}:{status}:{offset}:e19"),
            ],
            [InlineKeyboardButton("🌤 Завтра 10:00", callback_data=f"pt:{post_id}:{status}:{offset}:t10")],
            [InlineKeyboardButton("🚀 Опубликовать сейчас", callback_data=f"ppc:{post_id}:{status}:{offset}")],
            [InlineKeyboardButton("✍️ Редактировать вручную", callback_data=f"pm:{post_id}:{status}:{offset}")],
            [InlineKeyboardButton("🤖 Редактировать через LLM", callback_data=f"pa:{post_id}:{status}:{offset}")],
        ]
        if status == "draft":
            rows.append([InlineKeyboardButton("✅ В готовые", callback_data=f"pr:{post_id}:{status}:{offset}")])
        if _is_manual_queue_context(status):
            queue_filter = _queue_filter_from_context(status)
            rows.append([InlineKeyboardButton("🔙 К очереди", callback_data=f"mq:{queue_filter}:{offset}")])
        else:
            rows.append([InlineKeyboardButton("🔙 К списку", callback_data=f"pl:{status}:{offset}")])
        return InlineKeyboardMarkup(rows)

    def _publish_confirm_keyboard(self, post_id: str, status: str, offset: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Подтвердить публикацию", callback_data=f"ppy:{post_id}:{status}:{offset}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"ppn:{post_id}:{status}:{offset}")],
            ]
        )

    def _publish_reason_keyboard(self, post_id: str, status: str, offset: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data=f"ppn:{post_id}:{status}:{offset}")]])

    def _batch_publish_reason_keyboard(self, queue_filter: str, offset: int, mode: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data=f"mbn:{queue_filter}:{offset}:{mode}")]])

    def _batch_publish_confirm_keyboard(self, queue_filter: str, offset: int, mode: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Подтвердить пакетную публикацию", callback_data=f"mbc:{queue_filter}:{offset}:{mode}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"mbn:{queue_filter}:{offset}:{mode}")],
            ]
        )

    async def _send_to_telegram(self, context: ContextTypes.DEFAULT_TYPE, text: str, media_urls: list[str] | None) -> None:
        chat_id = settings.telegram_channel_id or settings.telegram_channel_username
        if not chat_id:
            raise RuntimeError("TELEGRAM_CHANNEL_ID or TELEGRAM_CHANNEL_USERNAME is required")

        if media_urls:
            photo_value = media_urls[0]
            if photo_value.startswith("tg://"):
                photo_value = photo_value.replace("tg://", "", 1)
            caption = (text or "")[:1020]
            remainder = (text or "")[1020:].strip()
            await context.bot.send_photo(chat_id=chat_id, photo=photo_value, caption=caption)
            for part in _split_text_for_telegram(remainder):
                await context.bot.send_message(chat_id=chat_id, text=part)
            return

        for part in _split_text_for_telegram(text):
            await context.bot.send_message(chat_id=chat_id, text=part)

    async def _publish_now(self, context: ContextTypes.DEFAULT_TYPE, post_id: str, reason: str | None = None) -> None:
        post = self._get_post(post_id)
        operator_note = _normalize_operator_note(reason or "")
        self.client.patch_post(post_id, {"status": "publishing", "last_error": None}).raise_for_status()
        try:
            await self._send_to_telegram(context, str(post.get("text") or ""), post.get("media_urls"))
            self.client.patch_post(post_id, {"status": "posted", "last_error": None}).raise_for_status()
            logger.info("manual_publish_success", extra={"post_id": post_id, "operator_note": operator_note})
        except Exception as exc:
            self.client.patch_post(post_id, {"status": "failed", "last_error": str(exc)[:500]}).raise_for_status()
            logger.exception("manual_publish_failed", extra={"post_id": post_id, "operator_note": operator_note})
            raise

    def _get_openai_client(self) -> Any:
        if self._openai_client is not None:
            return self._openai_client

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM editing")

        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError("openai package is required for LLM editing") from exc

        kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        self._openai_client = OpenAI(**kwargs)
        return self._openai_client

    def _rewrite_with_llm(self, original_text: str, instruction: str) -> str:
        client = self._get_openai_client()
        rewrite_prompt = (
            "Перепиши Telegram-пост по инструкции пользователя. "
            "Сохрани факты, ссылки, юридическую точность и общий смысл. "
            "Не добавляй выдуманные факты. Верни только новый текст поста без JSON и без markdown-блоков."
        )
        completion_kwargs: dict[str, Any]
        if self._use_max_tokens_param:
            completion_kwargs = {"max_tokens": 1500}
        else:
            completion_kwargs = {"max_completion_tokens": 1500}

        response = client.chat.completions.create(
            model=settings.news_model,
            messages=[
                {"role": "system", "content": rewrite_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Инструкция: {instruction}\n\n"
                        f"Исходный пост:\n{original_text}"
                    ),
                },
            ],
            temperature=0.3,
            **completion_kwargs,
        )

        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("LLM вернул пустой ответ")
        return content

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

    async def cmd_posts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            status = "scheduled"
            total, rows = self._load_posts(status=status, offset=0)
            await update.effective_message.reply_text(
                self._posts_text(total, rows, 0, status),
                reply_markup=self._posts_keyboard(total, rows, 0, status),
            )
        except Exception as exc:
            logger.exception("posts_list_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(f"Ошибка загрузки постов: {exc}")

    async def cmd_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            queue_filter = "due"
            total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=0)
            await update.effective_message.reply_text(
                self._manual_queue_text(total, rows, 0, queue_filter, due_total, scheduled_total),
                reply_markup=self._manual_queue_keyboard(total, rows, 0, queue_filter),
            )
        except Exception as exc:
            logger.exception("manual_queue_load_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(f"Ошибка загрузки ручной очереди: {exc}")

    async def cmd_cancel_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_admin(update):
            return
        context.user_data.pop(_STATE_PENDING_EDIT, None)
        context.user_data.pop(_STATE_DRAFT_EDIT, None)
        context.user_data.pop(_STATE_PENDING_PUBLISH_REASON, None)
        context.user_data.pop(_STATE_DRAFT_PUBLISH, None)
        context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
        context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
        await update.effective_message.reply_text("Режимы редактирования/публикации отменены.")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        await update.effective_message.reply_text(
            "Команды админ-бота:\n"
            "/admin — панель автоматизаций\n"
            "/controls — то же\n"
            "/status — статус очереди публикаций\n"
            "/posts — сгенерированные/готовые посты и ручная публикация\n"
            "/queue — ручная очередь публикации (в т.ч. пакетная)\n"
            "/cancel_edit — отменить редактирование\n"
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

    async def cb_posts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_admin(update):
            return

        query = update.callback_query
        await query.answer()
        data = query.data or ""

        try:
            if data.startswith("mq:"):
                queue_filter, offset = _parse_manual_queue_callback(data)
                total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
                await query.edit_message_text(
                    self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                    reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                )
                return

            if data.startswith("mbp:"):
                queue_filter, offset, mode = _parse_batch_publish_callback(data)
                if not _is_batch_mode_allowed(queue_filter, mode):
                    total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
                    await query.edit_message_text(
                        "Режимы топ-3/топ-5 доступны только для фильтра «К публикации сейчас».\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                    )
                    return
                total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
                selected_rows = rows
                limit = _batch_mode_limit(mode)
                if limit is not None:
                    selected_rows = rows[:limit]
                post_ids = [str(row.get("id")) for row in selected_rows if row.get("id")]
                if not post_ids:
                    await query.edit_message_text(
                        self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                    )
                    return
                context.user_data[_STATE_PENDING_BATCH_PUBLISH_REASON] = {
                    "queue_filter": queue_filter,
                    "offset": offset,
                    "mode": mode,
                    "post_ids": post_ids,
                }
                context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
                await query.edit_message_text(
                    "Пакетная публикация: шаг 1 из 2\n\n"
                    f"Выбрано постов: {len(post_ids)}\n"
                    f"Фильтр: {'к публикации сейчас' if queue_filter == 'due' else 'все готовые'}\n\n"
                    f"Режим: {_batch_mode_label(mode)}\n\n"
                    "Напишите причину пакетной публикации одним сообщением.",
                    reply_markup=self._batch_publish_reason_keyboard(queue_filter, offset, mode),
                )
                return

            if data.startswith("mbc:"):
                queue_filter, offset, mode = _parse_batch_publish_callback(data)
                draft = context.user_data.get(_STATE_DRAFT_BATCH_PUBLISH)
                if not draft:
                    await query.message.reply_text("Черновик пакетной публикации не найден. Запустите действие заново.")
                    return
                post_ids = [str(item) for item in draft.get("post_ids", []) if item]
                reason = _normalize_operator_note(str(draft.get("reason") or ""))
                if not post_ids or not reason:
                    await query.message.reply_text("Недостаточно данных для пакетной публикации. Запустите действие заново.")
                    return
                queue_filter = str(draft.get("queue_filter") or queue_filter)
                if queue_filter not in _MANUAL_QUEUE_FILTERS:
                    queue_filter = "due"
                offset = int(draft.get("offset") or offset)
                mode = str(draft.get("mode") or mode)
                if mode not in _BATCH_PUBLISH_MODES:
                    mode = "page"
                if not _is_batch_mode_allowed(queue_filter, mode):
                    context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
                    context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
                    total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
                    await query.edit_message_text(
                        "Пакетная публикация отменена: режим топ-3/топ-5 доступен только для фильтра «К публикации сейчас».\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                    )
                    return

                success_count = 0
                failed: list[str] = []
                for post_id in post_ids:
                    try:
                        await self._publish_now(context, post_id, reason)
                        success_count += 1
                    except Exception:
                        failed.append(post_id)

                context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
                total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
                result_lines = [
                    f"Пакетная публикация завершена.",
                    f"Успешно: {success_count}",
                    f"С ошибкой: {len(failed)}",
                    f"Режим: {_batch_mode_label(mode)}",
                ]
                if failed:
                    result_lines.append("ID с ошибками: " + ", ".join(failed[:5]))
                result_lines.append("")
                await query.edit_message_text(
                    "\n".join(result_lines)
                    + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                    reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                )
                return

            if data.startswith("mbn:"):
                queue_filter, offset, _ = _parse_batch_publish_callback(data)
                context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
                total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
                await query.edit_message_text(
                    "Пакетная публикация отменена.\n\n"
                    + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                    reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                )
                return

            if data.startswith("pl:"):
                status, offset = _parse_post_list_callback(data)
                if status not in _POST_LIST_STATUSES:
                    status = "scheduled"
                total, rows = self._load_posts(status=status, offset=offset)
                await query.edit_message_text(
                    self._posts_text(total, rows, offset, status),
                    reply_markup=self._posts_keyboard(total, rows, offset, status),
                )
                return

            if data.startswith("pv:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                post = self._get_post(post_id)
                await query.edit_message_text(
                    self._post_card_text(post),
                    reply_markup=self._post_card_keyboard(post_id, status, offset),
                )
                return

            if data.startswith("pt:"):
                _, post_id, status, offset_raw, slot = data.split(":", maxsplit=4)
                offset = int(offset_raw)
                publish_at_utc = _compute_quick_publish_at(slot)
                self.client.patch_post(
                    post_id,
                    {"status": "scheduled", "publish_at": publish_at_utc.isoformat()},
                ).raise_for_status()
                post = self._get_post(post_id)
                await query.edit_message_text(
                    f"Пост перепланирован: {_slot_label(slot)}.\n\n" + self._post_card_text(post),
                    reply_markup=self._post_card_keyboard(post_id, status, offset),
                )
                return

            if data.startswith("pr:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                self.client.patch_post(post_id, {"status": "scheduled"}).raise_for_status()
                total, rows = self._load_posts(status="scheduled", offset=0)
                await query.edit_message_text(
                    "Пост переведён в готовые (scheduled).\n\n" + self._posts_text(total, rows, 0, "scheduled"),
                    reply_markup=self._posts_keyboard(total, rows, 0, "scheduled"),
                )
                return

            if data.startswith("ba:"):
                _, action, status, offset_raw = data.split(":", maxsplit=3)
                if action != "ready":
                    await query.message.reply_text("Неизвестное пакетное действие.")
                    return
                offset = int(offset_raw)
                total, rows = self._load_posts(status=status, offset=offset)
                moved = 0
                for row in rows:
                    post_id = str(row.get("id"))
                    try:
                        self.client.patch_post(post_id, {"status": "scheduled"}).raise_for_status()
                        moved += 1
                    except Exception:
                        logger.exception("batch_move_failed", extra={"post_id": post_id, "from_status": status})
                total_after, rows_after = self._load_posts(status=status, offset=offset)
                await query.edit_message_text(
                    f"Готово: {moved} пост(ов) переведены в scheduled.\n\n"
                    + self._posts_text(total_after, rows_after, offset, status),
                    reply_markup=self._posts_keyboard(total_after, rows_after, offset, status),
                )
                return

            if data.startswith("ppc:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                post = self._get_post(post_id)
                title = str(post.get("title") or "Без заголовка").replace("\n", " ")
                context.user_data[_STATE_PENDING_PUBLISH_REASON] = {
                    "post_id": post_id,
                    "status": status,
                    "offset": offset,
                }
                context.user_data.pop(_STATE_DRAFT_PUBLISH, None)
                context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
                await query.edit_message_text(
                    "Ручная публикация: шаг 1 из 2\n\n"
                    f"Пост: {title[:120]}\n"
                    f"ID: {post_id}\n\n"
                    "Напишите одним сообщением причину ручной публикации "
                    "(например: «Срочный разбор для консультации с клиентом»).",
                    reply_markup=self._publish_reason_keyboard(post_id, status, offset),
                )
                return

            if data.startswith("ppn:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                context.user_data.pop(_STATE_PENDING_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_PUBLISH, None)
                context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
                post = self._get_post(post_id)
                await query.edit_message_text(
                    self._post_card_text(post),
                    reply_markup=self._post_card_keyboard(post_id, status, offset),
                )
                return

            if data.startswith("ppy:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                draft = context.user_data.get(_STATE_DRAFT_PUBLISH)
                if not draft or str(draft.get("post_id")) != post_id:
                    await query.message.reply_text("Причина публикации не найдена. Нажмите «Опубликовать сейчас» заново.")
                    return
                reason = _normalize_operator_note(str(draft.get("reason") or ""))
                if not reason:
                    await query.message.reply_text("Причина публикации пустая. Повторите запуск публикации.")
                    return
                await self._publish_now(context, post_id, reason)
                context.user_data.pop(_STATE_PENDING_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_PUBLISH, None)
                if _is_manual_queue_context(status):
                    queue_filter = _queue_filter_from_context(status)
                    total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
                    await query.edit_message_text(
                        f"Пост успешно опубликован вручную.\nПричина: {reason}\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                    )
                else:
                    total, rows = self._load_posts(status=status, offset=offset)
                    await query.edit_message_text(
                        f"Пост успешно опубликован вручную.\nПричина: {reason}\n\n"
                        + self._posts_text(total, rows, offset, status),
                        reply_markup=self._posts_keyboard(total, rows, offset, status),
                    )
                return

            if data.startswith("pm:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                context.user_data[_STATE_PENDING_EDIT] = {
                    "post_id": post_id,
                    "mode": "manual",
                    "offset": int(offset_raw),
                    "status": status,
                }
                context.user_data.pop(_STATE_PENDING_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_PUBLISH, None)
                context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
                context.user_data.pop(_STATE_DRAFT_EDIT, None)
                await query.message.reply_text(
                    "Пришлите новый текст поста одним сообщением.\n"
                    "Команда /cancel_edit — отмена."
                )
                return

            if data.startswith("pa:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                context.user_data[_STATE_PENDING_EDIT] = {
                    "post_id": post_id,
                    "mode": "ai",
                    "offset": int(offset_raw),
                    "status": status,
                }
                context.user_data.pop(_STATE_PENDING_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_PUBLISH, None)
                context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
                context.user_data.pop(_STATE_DRAFT_EDIT, None)
                await query.message.reply_text(
                    "Напишите инструкцию для LLM-редактирования.\n"
                    "Пример: «Сделай короче, добавь более сильный CTA и оставь юридические риски».\n"
                    "Команда /cancel_edit — отмена."
                )
                return

            if data.startswith("ps:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                draft = context.user_data.get(_STATE_DRAFT_EDIT)
                if not draft or str(draft.get("post_id")) != post_id:
                    await query.message.reply_text("Черновик редактирования не найден. Повторите редактирование.")
                    return

                payload = {"text": draft.get("text")}
                self.client.patch_post(post_id, payload).raise_for_status()
                context.user_data.pop(_STATE_DRAFT_EDIT, None)
                context.user_data.pop(_STATE_PENDING_EDIT, None)

                post = self._get_post(post_id)
                await query.edit_message_text(
                    "Изменения сохранены.\n\n" + self._post_card_text(post),
                    reply_markup=self._post_card_keyboard(post_id, status, int(offset_raw)),
                )
                return

            if data.startswith("px:"):
                _, status, offset_raw = data.split(":", maxsplit=2)
                offset = int(offset_raw)
                context.user_data.pop(_STATE_DRAFT_EDIT, None)
                context.user_data.pop(_STATE_PENDING_EDIT, None)
                if _is_manual_queue_context(status):
                    queue_filter = _queue_filter_from_context(status)
                    total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
                    await query.edit_message_text(
                        "Редактирование отменено.\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                    )
                else:
                    total, rows = self._load_posts(status=status, offset=offset)
                    await query.edit_message_text(
                        "Редактирование отменено.\n\n" + self._posts_text(total, rows, offset, status),
                        reply_markup=self._posts_keyboard(total, rows, offset, status),
                    )
                return
        except TelegramError as exc:
            logger.exception("posts_callback_telegram_error", extra={"callback_data": data, "error": str(exc)})
            await query.message.reply_text(f"Ошибка Telegram: {exc}")
        except Exception as exc:
            logger.exception("posts_callback_failed", extra={"callback_data": data, "error": str(exc)})
            await query.message.reply_text(f"Ошибка операции: {exc}")

    async def on_edit_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_admin(update):
            return

        message_text = (update.effective_message.text or "").strip()
        pending_batch_reason = context.user_data.get(_STATE_PENDING_BATCH_PUBLISH_REASON)
        if pending_batch_reason:
            reason = _normalize_operator_note(message_text)
            if not reason:
                await update.effective_message.reply_text("Причина не должна быть пустой. Пришлите сообщение ещё раз.")
                return

            queue_filter = str(pending_batch_reason.get("queue_filter") or "due")
            if queue_filter not in _MANUAL_QUEUE_FILTERS:
                queue_filter = "due"
            offset = int(pending_batch_reason.get("offset") or 0)
            mode = str(pending_batch_reason.get("mode") or "page")
            if mode not in _BATCH_PUBLISH_MODES:
                mode = "page"
            if not _is_batch_mode_allowed(queue_filter, mode):
                context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
                await update.effective_message.reply_text(
                    "Режимы топ-3/топ-5 доступны только в фильтре «К публикации сейчас». Запустите действие заново."
                )
                return
            post_ids = [str(item) for item in pending_batch_reason.get("post_ids", []) if item]
            if not post_ids:
                context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
                await update.effective_message.reply_text("Список постов пуст. Запустите пакетную публикацию заново.")
                return

            context.user_data[_STATE_DRAFT_BATCH_PUBLISH] = {
                "queue_filter": queue_filter,
                "offset": offset,
                "mode": mode,
                "post_ids": post_ids,
                "reason": reason,
            }
            context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
            await update.effective_message.reply_text(
                "Пакетная публикация: шаг 2 из 2\n\n"
                f"Постов к публикации: {len(post_ids)}\n"
                f"Режим: {_batch_mode_label(mode)}\n"
                f"Причина: {reason}\n\n"
                "Подтвердите запуск пакетной публикации:",
                reply_markup=self._batch_publish_confirm_keyboard(queue_filter, offset, mode),
            )
            return

        pending_publish_reason = context.user_data.get(_STATE_PENDING_PUBLISH_REASON)
        if pending_publish_reason:
            reason = _normalize_operator_note(message_text)
            if not reason:
                await update.effective_message.reply_text("Причина не должна быть пустой. Пришлите сообщение ещё раз.")
                return

            post_id = str(pending_publish_reason.get("post_id"))
            status = str(pending_publish_reason.get("status") or "scheduled")
            offset = int(pending_publish_reason.get("offset") or 0)
            context.user_data[_STATE_DRAFT_PUBLISH] = {
                "post_id": post_id,
                "status": status,
                "offset": offset,
                "reason": reason,
            }
            context.user_data.pop(_STATE_PENDING_PUBLISH_REASON, None)
            post = self._get_post(post_id)
            title = str(post.get("title") or "Без заголовка").replace("\n", " ")
            await update.effective_message.reply_text(
                "Ручная публикация: шаг 2 из 2\n\n"
                f"Пост: {title[:120]}\n"
                f"ID: {post_id}\n"
                f"Причина: {reason}\n\n"
                "Подтвердите публикацию в канал:",
                reply_markup=self._publish_confirm_keyboard(post_id, status, offset),
            )
            return

        pending = context.user_data.get(_STATE_PENDING_EDIT)
        if not pending:
            return

        instruction_or_text = message_text
        if not instruction_or_text:
            await update.effective_message.reply_text("Пустой текст не подходит. Пришлите сообщение ещё раз.")
            return

        post_id = str(pending.get("post_id"))
        mode = str(pending.get("mode") or "manual")
        offset = int(pending.get("offset") or 0)
        status = str(pending.get("status") or "scheduled")

        try:
            post = self._get_post(post_id)
            source_text = str(post.get("text") or "")
            if mode == "ai":
                new_text = self._rewrite_with_llm(source_text, instruction_or_text)
            else:
                new_text = instruction_or_text

            context.user_data[_STATE_DRAFT_EDIT] = {
                "post_id": post_id,
                "text": new_text,
                "offset": offset,
                "mode": mode,
                "status": status,
            }
            context.user_data.pop(_STATE_PENDING_EDIT, None)

            preview = new_text if len(new_text) <= 2500 else new_text[:2500] + "\n\n…"
            mode_label = "LLM" if mode == "ai" else "ручной"
            await update.effective_message.reply_text(
                f"Черновик ({mode_label}) готов.\nПроверьте и подтвердите сохранение:\n\n{preview}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("✅ Сохранить", callback_data=f"ps:{post_id}:{status}:{offset}")],
                        [InlineKeyboardButton("❌ Отмена", callback_data=f"px:{status}:{offset}")],
                    ]
                ),
            )
        except Exception as exc:
            logger.exception("edit_text_failed", extra={"post_id": post_id, "mode": mode, "error": str(exc)})
            await update.effective_message.reply_text(f"Ошибка редактирования: {exc}")

    def run(self) -> int:
        bot_token = settings.news_admin_bot_token or settings.telegram_bot_token
        if not bot_token:
            logger.error("NEWS_ADMIN_BOT_TOKEN (or TELEGRAM_BOT_TOKEN) is required")
            return 1
        if not settings.api_key_news:
            logger.error("API_KEY_NEWS is required")
            return 1
        if not self.admin_ids:
            logger.error("NEWS_ADMIN_IDS is empty; admin bot won't start")
            return 1

        app = Application.builder().token(bot_token).build()
        app.add_handler(CommandHandler("start", self.cmd_panel))
        app.add_handler(CommandHandler("admin", self.cmd_panel))
        app.add_handler(CommandHandler("controls", self.cmd_panel))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("posts", self.cmd_posts))
        app.add_handler(CommandHandler("queue", self.cmd_queue))
        app.add_handler(CommandHandler("cancel_edit", self.cmd_cancel_edit))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CallbackQueryHandler(self.cb_controls, pattern=r"^(refresh|status|all:[01]|set:[a-z0-9_.-]+:[01])$"))
        app.add_handler(
            CallbackQueryHandler(
                self.cb_posts,
                pattern=r"^(mq:(?:due|all):\d+|mq:\d+|mbp:(?:due|all):\d+(?::(?:page|top3|top5))?|mbc:(?:due|all):\d+(?::(?:page|top3|top5))?|mbn:(?:due|all):\d+(?::(?:page|top3|top5))?|pl:(?:draft|scheduled|failed):\d+|pl:\d+|pv:[0-9a-f-]{36}:(?:draft|scheduled|failed|mq_due|mq_all):\d+|pt:[0-9a-f-]{36}:(?:draft|scheduled|failed|mq_due|mq_all):\d+:(?:h1|e19|t10)|ppc:[0-9a-f-]{36}:(?:draft|scheduled|failed|mq_due|mq_all):\d+|ppy:[0-9a-f-]{36}:(?:draft|scheduled|failed|mq_due|mq_all):\d+|ppn:[0-9a-f-]{36}:(?:draft|scheduled|failed|mq_due|mq_all):\d+|pm:[0-9a-f-]{36}:(?:draft|scheduled|failed|mq_due|mq_all):\d+|pa:[0-9a-f-]{36}:(?:draft|scheduled|failed|mq_due|mq_all):\d+|pr:[0-9a-f-]{36}:draft:\d+|ps:[0-9a-f-]{36}:(?:draft|scheduled|failed|mq_due|mq_all):\d+|px:(?:draft|scheduled|failed|mq_due|mq_all):\d+|ba:ready:(?:draft|failed):\d+)$",
            )
        )
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_edit_text))

        logger.info("news_admin_bot_started", extra={"admins": sorted(self.admin_ids)})
        app.run_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)
        return 0


def main() -> int:
    return NewsAdminBot().run()


if __name__ == "__main__":
    raise SystemExit(main())
