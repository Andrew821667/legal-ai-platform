from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from telegram import (
    BotCommand,
    InlineKeyboardButton as _PTBInlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton as _PTBKeyboardButton,
    Message,
    MessageReactionCountUpdated,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageReactionHandler,
    MessageHandler,
    filters,
)

from news.core_client import CoreClient
from news.feedback import classify_comment_signal, summarize_reaction_counts
from news.generate import collect_generation_previews
from news.logging_config import setup_logging
from news.pipeline import extract_domain, normalize_rubric_to_pillar, parse_schedule_slots
from news.settings import settings
from news.source_catalog import active_source_specs, resolve_source_urls, source_catalog

setup_logging()
logger = logging.getLogger(__name__)


_POSTS_PAGE_SIZE = 8
_STATE_PENDING_EDIT = "pending_edit"
_STATE_DRAFT_EDIT = "draft_edit"
_STATE_PENDING_PUBLISH_REASON = "pending_publish_reason"
_STATE_DRAFT_PUBLISH = "draft_publish"
_STATE_PENDING_BATCH_PUBLISH_REASON = "pending_batch_publish_reason"
_STATE_DRAFT_BATCH_PUBLISH = "draft_batch_publish"
_STATE_PENDING_CREATE = "pending_create"
_STATE_DRAFT_CREATE = "draft_create"
_STATE_PENDING_DAY_PUBLISH_REASON = "pending_day_publish_reason"
_STATE_DRAFT_DAY_PUBLISH = "draft_day_publish"
_STATE_GENERATION_PREVIEWS = "generation_previews"
_STATE_PENDING_DELETE_REASON = "pending_delete_reason"
_CREATE_EDIT_STEPS = {"edit_title", "edit_text", "edit_ai"}
_POST_LIST_STATUSES = ("draft", "review", "scheduled", "posted", "failed")
_MANUAL_QUEUE_FILTERS = ("due", "all")
_BATCH_PUBLISH_MODES = ("page", "top3", "top5")
_MAIN_MENU_PANEL = "🏠 Панель"
_MAIN_MENU_CREATE = "➕ Создать"
_MAIN_MENU_CALENDAR = "🗓 Календарь"
_MAIN_MENU_SECTIONS = "📚 Разделы"
_MAIN_MENU_HELP = "ℹ️ Помощь"

_BUTTON_STYLE_PRIMARY = "primary"
_BUTTON_STYLE_SUCCESS = "success"
_BUTTON_STYLE_DANGER = "danger"
_NEWS_ADMIN_BUTTON_ICON_ENV = "NEWS_ADMIN_BUTTON_ICON_MAP"
_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_POST_CACHE_TTL_SECONDS = 12
_QUEUE_CACHE_TTL_SECONDS = 15

_PILLAR_LABELS = {
    "regulation": "AI в праве и регулирование",
    "case": "Кейсы внедрения в юрфункции",
    "implementation": "Автоматизация юрфункции и legal ops",
    "tools": "AI-инструменты для практики юриста",
    "market": "Рынок Legal AI и legal tech",
}
_RUBRIC_LABELS = {
    "ai_law": "AI law / регулирование",
    "compliance": "Комплаенс и governance",
    "privacy": "ПДн / privacy",
    "contracts": "Договорная автоматизация",
    "litigation": "Суды и споры",
    "legal_ops": "Legal ops",
    "regulation": "AI-регулирование",
    "market": "Рынок legal tech",
    "manual": "Ручные посты",
}
_PILLAR_RUBRICS = {
    "regulation": ("ai_law", "compliance", "privacy", "litigation", "regulation"),
    "case": ("case",),
    "implementation": ("legal_ops", "contracts", "implementation", "manual"),
    "tools": ("tools",),
    "market": ("market",),
}
_TELEGRAM_CHANNEL_NOTES = {
    "allthingslegal": "Международная повестка legal tech, legal AI, legal ops и рынка юридических технологий.",
    "legal_tech": "Русскоязычные новости и кейсы по legal tech, автоматизации юристов и AI-сервисам.",
    "law_gpt": "Практическое применение LLM и AI-инструментов в работе юриста и юридической команды.",
    "ai_newz": "Широкий AI-канал. Используется только как upstream-источник с жесткой фильтрацией по юридической релевантности.",
    "anthropicai": "Официальный канал Anthropic с релизами моделей, исследованиями и AI-подходами.",
    "googleai": "Официальный канал Google AI с модельными и исследовательскими обновлениями.",
    "openai_ru": "Русскоязычный AI-канал по практическому использованию моделей и инструментов.",
    "ai_machinelearning_big_data": "AI / ML-канал про крупные отраслевые новости и сигналы рынка.",
}
_TELEGRAM_CHANNEL_GROUPS = {
    "allthingslegal": "legal",
    "legal_tech": "legal",
    "law_gpt": "legal",
    "ai_newz": "ai",
    "anthropicai": "ai",
    "googleai": "ai",
    "openai_ru": "ai",
    "ai_machinelearning_big_data": "ai",
}


def _is_hidden_deleted_post(row: dict[str, Any]) -> bool:
    last_error = str(row.get("last_error") or "").strip().lower()
    return last_error.startswith("deleted_irrelevant")


def _status_label(status: str) -> str:
    if _is_calendar_context(status):
        return "🗓 Календарь публикаций"
    mapping = {
        "draft": "📝 Авторские черновики",
        "review": "🟡 На проверке",
        "scheduled": "✅ Готовые к публикации",
        "posted": "📤 Опубликованные",
        "failed": "❌ Ошибки публикации",
    }
    return mapping.get(status, status)


def _status_badge(status: str) -> str:
    mapping = {
        "draft": "📝",
        "review": "🟡",
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


def _pillar_label(pillar: str) -> str:
    return _PILLAR_LABELS.get(pillar, pillar)


def _rubric_label(rubric: str) -> str:
    normalized = (rubric or "").strip().lower()
    return _RUBRIC_LABELS.get(normalized, normalized or "без рубрики")


def _source_profile(domain: str) -> tuple[str, str]:
    for spec in source_catalog(settings).values():
        if spec.domain == domain:
            return spec.name, spec.note
    return domain, "Специализированный источник без отдельного профиля"


def _source_control_key(source_key: str) -> str:
    return f"news.source.{source_key}.enabled"


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


def _theme_context(pillar: str) -> str:
    return f"th_{pillar}"


def _is_theme_context(context: str) -> bool:
    return context.startswith("th_")


def _theme_from_context(context: str) -> str:
    return context.removeprefix("th_")


def _source_context(domain: str) -> str:
    return f"src_{domain}"


def _is_source_context(context: str) -> bool:
    return context.startswith("src_")


def _source_from_context(context: str) -> str:
    return context.removeprefix("src_")


def _telegram_channel_slug(value: str) -> str:
    return value.strip().lstrip("@").lower()


def _telegram_channel_label(value: str) -> str:
    return f"@{_telegram_channel_slug(value)}"


def _telegram_channel_note(value: str) -> str:
    return _TELEGRAM_CHANNEL_NOTES.get(_telegram_channel_slug(value), "Подключенный Telegram-канал без отдельного профиля.")


def _telegram_channel_group(value: str) -> str:
    return _TELEGRAM_CHANNEL_GROUPS.get(_telegram_channel_slug(value), "ai")


def _telegram_channel_group_label(group: str) -> str:
    if group == "legal":
        return "Legal AI / Legal Tech"
    return "Широкий AI"


def _strip_html_markup(text: str) -> str:
    normalized = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(normalized)


def _telegram_channel_control_key(slug: str) -> str:
    return f"news.telegram_channel.{_telegram_channel_slug(slug)}.enabled"


def _humanize_interval(seconds: int) -> str:
    if seconds <= 0:
        return "выключен"
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"каждые {hours} ч"
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"каждые {minutes} мин"
    return f"каждые {seconds} сек"


def _calendar_context(date_iso: str) -> str:
    return f"cal_{date_iso.replace('-', '')}"


def _is_calendar_context(context: str) -> bool:
    return context.startswith("cal_") and len(context) == 12


def _calendar_date_from_context(context: str) -> str:
    raw = context.removeprefix("cal_")
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def _slot_token(hour: int, minute: int) -> str:
    return f"{hour:02d}{minute:02d}"


def _slot_from_token(token: str) -> tuple[int, int]:
    return int(token[:2]), int(token[2:4])


def _normalize_operator_note(note: str, limit: int = 500) -> str:
    normalized = " ".join((note or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _format_workers_status(payload: dict[str, Any]) -> str:
    any_active = bool(payload.get("any_active"))
    workers = payload.get("workers") or []

    lines = [
        "Статус воркеров",
        "",
        f"Активные воркеры: {'да' if any_active else 'нет'}",
    ]

    if not workers:
        lines.append("Список пуст.")
        return "\n".join(lines)

    lines.append("")
    for row in workers[:20]:
        worker_id = str(row.get("worker_id") or "unknown")
        active = bool(row.get("active"))
        mark = "🟢" if active else "⚪"
        last_seen = str(row.get("last_seen_at") or "n/a")
        lines.append(f"{mark} {worker_id}")
        lines.append(f"   last_seen: {last_seen}")

    return "\n".join(lines)


def _button_api_kwargs(
    *,
    style: str | None = None,
    icon_custom_emoji_id: str | None = None,
    api_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    merged: dict[str, Any] = dict(api_kwargs or {})
    if style:
        merged["style"] = style
    if icon_custom_emoji_id:
        merged["icon_custom_emoji_id"] = icon_custom_emoji_id
    return merged or None


def _parse_button_icon_map(raw: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for chunk in (raw or "").split(","):
        item = chunk.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", maxsplit=1)
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            mapping[key] = value
    return mapping


def _read_env_value(env_file: Path, key: str) -> str:
    if not env_file.exists():
        return ""
    prefix = f"{key}="
    for line in env_file.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if item.startswith(prefix):
            return item[len(prefix):].strip()
    return ""


def _normalize_button_text(text: str | None) -> str:
    normalized = " ".join((text or "").split())
    if not normalized:
        return ""
    def _has_wordish_char(token: str) -> bool:
        for char in token:
            lower = char.lower()
            if char.isdigit() or ("a" <= lower <= "z") or ("а" <= lower <= "я") or lower == "ё":
                return True
        return False
    tokens = normalized.split(" ")
    while len(tokens) > 1 and not _has_wordish_char(tokens[0]):
        tokens.pop(0)
    result = " ".join(tokens).strip()
    return result or normalized


@lru_cache(maxsize=1)
def _button_icon_map() -> dict[str, str]:
    raw = os.getenv(_NEWS_ADMIN_BUTTON_ICON_ENV, "").strip()
    if not raw:
        raw = _read_env_value(_ROOT_ENV_FILE, _NEWS_ADMIN_BUTTON_ICON_ENV)
    return _parse_button_icon_map(raw)


def _infer_button_icon_key(text: str | None) -> str | None:
    label = _normalize_button_text(text)
    normalized = label.lower()
    if not normalized:
        return None
    exact = {
        "панель": "panel",
        "создать": "create",
        "разделы": "sections",
        "календарь": "calendar",
        "помощь": "help",
        "автоматизация": "automation",
        "сводка": "summary",
        "воркеры": "workers",
    }
    if normalized in exact:
        return exact[normalized]
    contains_rules = (
        ("на проверке", "review"),
        ("черновики", "drafts"),
        ("готовые", "ready"),
        ("опубликованные", "posted"),
        ("ошибки", "failed"),
        ("очередь", "queue"),
        ("подтвердить", "confirm"),
        ("сохранить", "save"),
        ("опубликовать", "publish"),
        ("отмен", "cancel"),
        ("очист", "cleanup"),
        ("сброс", "reset"),
        ("обновить", "refresh"),
    )
    for token, key in contains_rules:
        if token in normalized:
            return key
    return None


def _infer_button_style(text: str | None) -> str | None:
    label = (text or "").strip()
    if not label:
        return None
    normalized = _normalize_button_text(label).lower()
    if label.startswith("✅") or any(
        token in normalized
        for token in (
            "подтверд",
            "сохранить",
            "опубликовать",
            "включить",
            "создать",
        )
    ):
        return _BUTTON_STYLE_SUCCESS
    if label.startswith(("❌", "⛔", "🗑", "⚠️")) or any(
        token in normalized
        for token in (
            "отмен",
            "отключ",
            "очист",
            "сброс",
            "закрыть",
            "ошибки",
        )
    ):
        return _BUTTON_STYLE_DANGER
    return None


def InlineKeyboardButton(text: str, *args: Any, **kwargs: Any) -> _PTBInlineKeyboardButton:
    style = kwargs.pop("style", None) or _infer_button_style(text)
    icon_custom_emoji_id = kwargs.pop("icon_custom_emoji_id", None)
    if icon_custom_emoji_id is None:
        icon_key = _infer_button_icon_key(text)
        if icon_key:
            icon_custom_emoji_id = _button_icon_map().get(icon_key)
    api_kwargs = kwargs.pop("api_kwargs", None)
    display_text = _normalize_button_text(text) if icon_custom_emoji_id else text
    return _PTBInlineKeyboardButton(
        display_text,
        *args,
        api_kwargs=_button_api_kwargs(
            style=style,
            icon_custom_emoji_id=icon_custom_emoji_id,
            api_kwargs=api_kwargs,
        ),
        **kwargs,
    )


def KeyboardButton(text: str, *args: Any, **kwargs: Any) -> _PTBKeyboardButton:
    style = kwargs.pop("style", None) or _infer_button_style(text)
    icon_custom_emoji_id = kwargs.pop("icon_custom_emoji_id", None)
    if icon_custom_emoji_id is None:
        icon_key = _infer_button_icon_key(text)
        if icon_key:
            icon_custom_emoji_id = _button_icon_map().get(icon_key)
    api_kwargs = kwargs.pop("api_kwargs", None)
    display_text = _normalize_button_text(text) if icon_custom_emoji_id else text
    return _PTBKeyboardButton(
        display_text,
        *args,
        api_kwargs=_button_api_kwargs(
            style=style,
            icon_custom_emoji_id=icon_custom_emoji_id,
            api_kwargs=api_kwargs,
        ),
        **kwargs,
    )


def _inline_button(
    text: str,
    *,
    callback_data: str | None = None,
    url: str | None = None,
    style: str | None = None,
    icon_custom_emoji_id: str | None = None,
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text,
        callback_data=callback_data,
        url=url,
        style=style,
        icon_custom_emoji_id=icon_custom_emoji_id,
    )


def _reply_button(
    text: str,
    *,
    request_contact: bool | None = None,
    style: str | None = None,
    icon_custom_emoji_id: str | None = None,
) -> KeyboardButton:
    return KeyboardButton(
        text,
        request_contact=request_contact,
        style=style,
        icon_custom_emoji_id=icon_custom_emoji_id,
    )


def _button_text_equals(text: str | None, expected: str) -> bool:
    return _normalize_button_text(text).casefold() == _normalize_button_text(expected).casefold()


def _is_scope_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return bool(status_code == 403)


def _main_menu_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [
                _reply_button(_MAIN_MENU_PANEL),
                _reply_button(_MAIN_MENU_CREATE),
            ],
            [
                _reply_button(_MAIN_MENU_CALENDAR),
                _reply_button(_MAIN_MENU_SECTIONS),
            ],
            [_reply_button(_MAIN_MENU_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите раздел админ-панели",
    )


class NewsAdminBot:
    def __init__(self) -> None:
        self.admin_ids = _parse_admin_ids(settings.news_admin_ids)
        self.client = CoreClient(settings.core_api_url, settings.api_key_news)
        admin_key = (settings.api_key_admin or "").strip() or settings.api_key_news
        self.admin_client = CoreClient(settings.core_api_url, admin_key)
        self._openai_client: Any | None = None
        self._use_max_tokens_param = "deepseek" in (settings.openai_base_url or "").lower()
        self._controls_cache: tuple[datetime, list[dict[str, Any]]] | None = None
        self._queue_snapshot_cache: tuple[datetime, tuple[dict[str, int], str]] | None = None
        self._posts_cache: dict[tuple[str, bool, int], tuple[datetime, list[dict[str, Any]]]] = {}

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

    def _load_controls(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        if not force_refresh and self._controls_cache is not None:
            loaded_at, cached_rows = self._controls_cache
            if (now - loaded_at).total_seconds() <= 30:
                return list(cached_rows)

        response = self.client.list_automation_controls(scope="news")
        response.raise_for_status()
        rows = response.json()
        rows.sort(key=lambda row: row.get("key", ""))
        self._controls_cache = (now, list(rows))
        return rows

    def _invalidate_post_caches(self) -> None:
        self._queue_snapshot_cache = None
        self._posts_cache.clear()

    def _list_posts_rows(
        self,
        *,
        status: str,
        newest_first: bool = False,
        limit: int = 100,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        cache_key = (status, newest_first, limit)
        now = datetime.now(timezone.utc)
        if not force_refresh:
            cached = self._posts_cache.get(cache_key)
            if cached and (now - cached[0]).total_seconds() <= _POST_CACHE_TTL_SECONDS:
                return list(cached[1])

        response = self.client.list_posts(limit=limit, status=status, newest_first=newest_first)
        response.raise_for_status()
        rows = [row for row in response.json() if not _is_hidden_deleted_post(row)]
        self._posts_cache[cache_key] = (now, list(rows))
        return rows

    async def _safe_edit_message_text(
        self,
        query,
        text: str,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> bool:
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
            return True
        except TelegramError as exc:
            if "message is not modified" in str(exc).lower():
                logger.info("admin_message_not_modified", extra={"callback_data": query.data})
                return False
            raise

    def _controls_map(self, *, force_refresh: bool = False) -> dict[str, bool]:
        rows = self._load_controls(force_refresh=force_refresh)
        return {str(row.get("key") or ""): bool(row.get("enabled", True)) for row in rows}

    def _source_enabled_map(self, *, force_refresh: bool = False) -> dict[str, bool]:
        controls = self._controls_map(force_refresh=force_refresh)
        return {
            key: controls.get(_source_control_key(key), True)
            for key in source_catalog(settings)
        }

    def _controls_text(self, controls: list[dict[str, Any]]) -> str:
        control_map = {str(row.get("key") or ""): bool(row.get("enabled", True)) for row in controls}
        autopilot_enabled = control_map.get("news.generate.enabled", True) and control_map.get(
            "news.publish.enabled", True
        )
        feedback_collect = control_map.get("news.feedback.collect.enabled", True)
        feedback_guard = control_map.get("news.feedback.guard.enabled", True)
        discussion_ready = bool((settings.news_discussion_chat_id or "").strip() or (settings.news_discussion_chat_username or "").strip())

        lines = [
            "Автоматизация news",
            "",
            f"Автопилот контента: {'🟢 включен' if autopilot_enabled else '🔴 выключен'}",
            f"Генерация: {_humanize_interval(settings.news_generate_interval_seconds)}; лимит за цикл {settings.news_generate_limit}",
            f"Публикация: {_humanize_interval(settings.news_publish_interval_seconds)}",
            f"Сбор feedback: {'🟢' if feedback_collect else '🔴'}",
            f"Защита по feedback: {'🟢' if feedback_guard else '🔴'}",
            f"Discussion group для feedback: {'🟢 настроена' if discussion_ready else '🔴 не настроена'}",
            "",
        ]
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

    @staticmethod
    def _format_feedback_snapshot(snapshot: dict[str, Any] | None) -> str:
        data = snapshot or {}
        if not data:
            return "Feedback: пока нет сигналов."

        lines = [
            "Сводка feedback",
            f"score: {data.get('score', 0)}",
            f"реакции: +{data.get('reaction_positive', 0)} / -{data.get('reaction_negative', 0)} / всего {data.get('reaction_total', 0)}",
            f"комментарии: +{data.get('comments_positive', 0)} / -{data.get('comments_negative', 0)} / всего {data.get('comments_total', 0)}",
        ]
        top_reactions = data.get("top_reactions") or []
        if top_reactions:
            summary = ", ".join(
                f"{row.get('reaction')}×{row.get('count')}" for row in top_reactions[:4] if row.get("reaction")
            )
            if summary:
                lines.append(f"топ реакций: {summary}")
        negative_comments = data.get("recent_negative_comments") or []
        if negative_comments:
            lines.append("свежие негативные сигналы:")
            for item in negative_comments[:2]:
                lines.append(f"- {str(item)[:180]}")
        return "\n".join(lines)

    @staticmethod
    def _discussion_chat_matches(message: Message) -> bool:
        expected_id = (settings.news_discussion_chat_id or "").strip()
        expected_username = (settings.news_discussion_chat_username or "").strip().lstrip("@").lower()
        if expected_id and str(getattr(message.chat, "id", "")) == expected_id:
            return True
        if expected_username:
            username = (getattr(message.chat, "username", "") or "").lstrip("@").lower()
            return username == expected_username
        return True

    @staticmethod
    def _extract_channel_post_message_id(reply_message: Message | None) -> int | None:
        if reply_message is None:
            return None
        forward_origin = getattr(reply_message, "forward_origin", None)
        message_id = getattr(forward_origin, "message_id", None)
        if isinstance(message_id, int) and message_id > 0:
            return message_id
        external_reply = getattr(reply_message, "external_reply", None)
        external_message_id = getattr(external_reply, "message_id", None)
        if isinstance(external_message_id, int) and external_message_id > 0:
            return external_message_id
        if getattr(reply_message, "is_automatic_forward", False):
            fallback_id = getattr(reply_message, "message_id", None)
            if isinstance(fallback_id, int) and fallback_id > 0:
                return fallback_id
        return None

    def _feedback_collection_enabled(self) -> bool:
        try:
            controls = self._controls_map()
        except Exception:
            return True
        return controls.get("news.feedback.collect.enabled", True)

    def _panel_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    _inline_button("📚 Разделы", callback_data="sections"),
                    _inline_button("➕ Создать", callback_data="cn:start", style=_BUTTON_STYLE_SUCCESS),
                ],
                [
                    _inline_button("🗓 Календарь", callback_data="cal:summary"),
                    _inline_button("⚙️ Генерация", callback_data="sec:generate"),
                ],
                [
                    _inline_button("📊 Сводка", callback_data="status"),
                    _inline_button("🤖 Автоматизация", callback_data="automation"),
                ],
                [_inline_button("🔄 Обновить", callback_data="refresh")],
            ]
        )

    def _sections_text(self, counts: dict[str, int], next_publish: str) -> str:
        return (
            "Разделы редактора\n\n"
            "Навигация разбита на отдельные экраны: рабочие списки, тематики, источники и ручная генерация.\n\n"
            f"📝 Черновики: {counts.get('draft', -1)}\n"
            f"🟡 На проверке: {counts.get('review', -1)}\n"
            f"✅ Готовые: {counts.get('scheduled', -1)}\n"
            f"📤 Опубликованные: {counts.get('posted', -1)}\n"
            f"❌ Ошибки: {counts.get('failed', -1)}\n"
            f"⏳ В публикации: {counts.get('publishing', -1)}\n\n"
            f"Следующая публикация: {next_publish}"
        )

    def _sections_keyboard(self, counts: dict[str, int]) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    _inline_button("📂 Рабочие списки", callback_data="sec:worklists"),
                    _inline_button("🧭 Тематики", callback_data="sec:themes"),
                ],
                [
                    _inline_button("📰 Источники", callback_data="sec:sources"),
                    _inline_button("⚙️ Генерация", callback_data="sec:generate"),
                ],
                [
                    _inline_button("🚀 Ручная очередь", callback_data="mq:due:0"),
                    _inline_button("🗓 Календарь", callback_data="cal:summary"),
                ],
                [_inline_button("🏠 Панель", callback_data="refresh")],
            ]
        )

    def _worklists_keyboard(self, counts: dict[str, int]) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    _inline_button(f"📝 Черновики ({counts.get('draft', 0)})", callback_data="pl:draft:0"),
                    _inline_button(f"🟡 На проверке ({counts.get('review', 0)})", callback_data="pl:review:0"),
                ],
                [
                    _inline_button(
                        f"✅ Готовые ({counts.get('scheduled', 0)})",
                        callback_data="pl:scheduled:0",
                        style=_BUTTON_STYLE_SUCCESS,
                    ),
                    _inline_button(f"📤 Опубликованные ({counts.get('posted', 0)})", callback_data="pl:posted:0"),
                ],
                [
                    _inline_button(
                        f"❌ Ошибки ({counts.get('failed', 0)})",
                        callback_data="pl:failed:0",
                        style=_BUTTON_STYLE_DANGER,
                    ),
                    _inline_button("🚀 Ручная очередь", callback_data="mq:due:0"),
                ],
                [_inline_button("🔙 К разделам", callback_data="sections")],
            ]
        )

    def _worklists_text(self, counts: dict[str, int], next_publish: str) -> str:
        return (
            "Рабочие списки\n\n"
            f"📝 Черновики: {counts.get('draft', -1)}\n"
            f"🟡 На проверке: {counts.get('review', -1)}\n"
            f"✅ Готовые: {counts.get('scheduled', -1)}\n"
            f"📤 Опубликованные: {counts.get('posted', -1)}\n"
            f"❌ Ошибки: {counts.get('failed', -1)}\n\n"
            f"Следующая публикация: {next_publish}"
        )

    def _sources_text(self) -> str:
        enabled_map = self._source_enabled_map()
        catalog = source_catalog(settings)
        counts = self._source_stats()
        active_count = sum(1 for key, spec in catalog.items() if enabled_map.get(key, True) and spec.integrated)
        lines = [
            "Источники новостей",
            "",
            "Здесь показан общий каталог источников.",
            "Нажмите на источник, чтобы открыть карточку с описанием, статусом, URL и связанными постами.",
            "",
            f"Активных интегрированных источников: {active_count}",
            f"Всего источников в каталоге: {len(catalog)}",
            "",
        ]
        for index, spec in enumerate(catalog.values(), start=1):
            row = counts.get(spec.key, {})
            enabled = enabled_map.get(spec.key, True)
            if not spec.integrated:
                badge = "🟡"
                status = "ожидает настройки"
            elif enabled:
                badge = "✅"
                status = "включен"
            else:
                badge = "☐"
                status = "выключен"
            total = sum(int(row.get(item, 0)) for item in ("review", "scheduled", "posted", "failed"))
            lines.append(f"{index}. {badge} {spec.name} [{spec.kind}]")
            lines.append(f"   {status}; постов в истории: {total}")
        return "\n".join(lines)

    def _sources_keyboard(self) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        specs = list(source_catalog(settings).values())
        for index in range(0, len(specs), 2):
            chunk = specs[index : index + 2]
            rows.append(
                [
                    _inline_button(
                        spec.name[:20],
                        callback_data=f"srd:{spec.key}",
                    )
                    for spec in chunk
                ]
            )
        rows.append([_inline_button("⚙️ Генерация", callback_data="sec:generate")])
        rows.append([_inline_button("🔙 К разделам", callback_data="sections")])
        return InlineKeyboardMarkup(rows)

    def _source_stats(self) -> dict[str, dict[str, int]]:
        catalog = source_catalog(settings)
        stats: dict[str, dict[str, int]] = {key: {"review": 0, "scheduled": 0, "posted": 0, "failed": 0} for key in catalog}
        for status in ("review", "scheduled", "posted", "failed"):
            for row in self._list_posts_rows(status=status, newest_first=True, limit=100):
                source_url = str(row.get("source_url") or "")
                source_feed_url = str(row.get("source_feed_url") or "")
                domain = extract_domain(source_url)
                if domain == "t.me":
                    stats.setdefault("telegram_channels", {"review": 0, "scheduled": 0, "posted": 0, "failed": 0})
                    stats["telegram_channels"][status] = stats["telegram_channels"].get(status, 0) + 1
                    continue
                for key, spec in catalog.items():
                    matched = False
                    if spec.url and source_feed_url and source_feed_url == spec.url:
                        matched = True
                    elif spec.url and source_url and source_url == spec.url:
                        matched = True
                    elif spec.domain and domain and spec.domain == domain:
                        matched = True
                    if matched:
                        stats.setdefault(key, {"review": 0, "scheduled": 0, "posted": 0, "failed": 0})
                        stats[key][status] = stats[key].get(status, 0) + 1
                        break
        return stats

    def _telegram_channel_enabled_map(self, force_refresh: bool = False) -> dict[str, bool]:
        controls = self._controls_map(force_refresh=force_refresh)
        result: dict[str, bool] = {}
        for channel in settings.telegram_channels_list:
            slug = _telegram_channel_slug(channel)
            result[slug] = controls.get(_telegram_channel_control_key(slug), True)
        return result

    def _telegram_channel_history_counts(self) -> dict[str, dict[str, int]]:
        stats: dict[str, dict[str, int]] = {}
        for status in ("review", "scheduled", "posted", "failed"):
            for row in self._list_posts_rows(status=status, newest_first=True, limit=100):
                source_url = str(row.get("source_url") or "")
                if extract_domain(source_url) != "t.me":
                    continue
                path_parts = [part for part in source_url.strip("/").split("/") if part]
                if not path_parts:
                    continue
                slug = _telegram_channel_slug(path_parts[-1])
                bucket = stats.setdefault(slug, {"review": 0, "scheduled": 0, "posted": 0, "failed": 0})
                bucket[status] = bucket.get(status, 0) + 1
        return stats

    def _source_detail_text(self, source_key: str) -> str:
        spec = source_catalog(settings).get(source_key)
        if spec is None:
            return "Источник не найден."
        enabled_map = self._source_enabled_map()
        counts = self._source_stats().get(source_key, {})
        if not spec.integrated:
            status = "🟡 Требует настройки"
        elif enabled_map.get(source_key, True):
            status = "✅ Включен"
        else:
            status = "☐ Выключен"
        lines = [
            f"Источник: {spec.name}",
            "",
            f"Тип: {spec.kind}",
            f"Статус: {status}",
            "",
            f"Описание: {spec.note}",
        ]
        if spec.url:
            lines.extend(["", f"URL: {spec.url}"])
        if spec.domain:
            lines.append(f"Домен: {spec.domain}")
        if source_key == "telegram_channels":
            channels = settings.telegram_channels_list
            channel_enabled = self._telegram_channel_enabled_map()
            lines.extend(["", f"Подключенные каналы: {len(channels)}"])
            for group in ("legal", "ai"):
                group_channels = [channel for channel in channels if _telegram_channel_group(channel) == group]
                if not group_channels:
                    continue
                lines.append(f"• {_telegram_channel_group_label(group)}:")
                for channel in group_channels:
                    slug = _telegram_channel_slug(channel)
                    badge = "✅" if channel_enabled.get(slug, True) else "☐"
                    lines.append(f"  {badge} {_telegram_channel_label(channel)}")
        lines.extend(
            [
                "",
                "Посты в истории:",
                f"• На проверке: {counts.get('review', 0)}",
                f"• Готовые: {counts.get('scheduled', 0)}",
                f"• Опубликованные: {counts.get('posted', 0)}",
                f"• Ошибки: {counts.get('failed', 0)}",
            ]
        )
        return "\n".join(lines)

    def _source_detail_keyboard(self, source_key: str) -> InlineKeyboardMarkup:
        spec = source_catalog(settings).get(source_key)
        enabled_map = self._source_enabled_map()
        enabled = enabled_map.get(source_key, True)
        rows: list[list[InlineKeyboardButton]] = [
            [
                _inline_button(
                    "☐ Выключить" if enabled else "✅ Включить",
                    callback_data=f"srt:{source_key}",
                    style=_BUTTON_STYLE_SUCCESS if not enabled else None,
                )
            ]
        ]
        if spec and spec.integrated:
            rows.append([_inline_button("📄 Посты по источнику", callback_data=f"src:{source_key}:0")])
        if source_key == "telegram_channels":
            channels = settings.telegram_channels_list
            channel_enabled = self._telegram_channel_enabled_map()
            for group in ("legal", "ai"):
                group_channels = [channel for channel in channels if _telegram_channel_group(channel) == group]
                if not group_channels:
                    continue
                rows.append([_inline_button(_telegram_channel_group_label(group), callback_data="noop")])
                for index in range(0, len(group_channels), 2):
                    chunk = group_channels[index : index + 2]
                    rows.append(
                        [
                            _inline_button(
                                f"{'✅' if channel_enabled.get(_telegram_channel_slug(item), True) else '☐'} {_telegram_channel_label(item)}",
                                callback_data=f"stc:{_telegram_channel_slug(item)}",
                            )
                            for item in chunk
                        ]
                    )
        rows.append([_inline_button("🔙 К источникам", callback_data="sec:sources")])
        return InlineKeyboardMarkup(rows)

    def _telegram_channel_detail_text(self, slug: str) -> str:
        normalized = _telegram_channel_slug(slug)
        label = f"@{normalized}"
        enabled = self._telegram_channel_enabled_map().get(normalized, True)
        counts = self._telegram_channel_history_counts().get(normalized, {})
        lines = [
            f"Telegram-канал: {label}",
            "",
            f"Группа: {_telegram_channel_group_label(_telegram_channel_group(normalized))}",
            "",
            f"Статус: {'✅ Включен' if enabled else '☐ Выключен'}",
            "",
            f"Описание: {_telegram_channel_note(normalized)}",
            "",
            "Роль в контуре:",
            "• используется как дополнительный специализированный источник идей и сигналов",
            "• проходит через topical filter и relevance gate",
            "• не должен тянуть в канал общий AI-шум без связи с правом и юрфункцией",
            "",
            "Посты в истории:",
            f"• На проверке: {counts.get('review', 0)}",
            f"• Готовые: {counts.get('scheduled', 0)}",
            f"• Опубликованные: {counts.get('posted', 0)}",
            f"• Ошибки: {counts.get('failed', 0)}",
            "",
            f"Ссылка: https://t.me/{normalized}",
        ]
        return "\n".join(lines)

    def _telegram_channel_detail_keyboard(self, slug: str) -> InlineKeyboardMarkup:
        normalized = _telegram_channel_slug(slug)
        enabled = self._telegram_channel_enabled_map().get(normalized, True)
        return InlineKeyboardMarkup(
            [
                [
                    _inline_button(
                        "☐ Выключить" if enabled else "✅ Включить",
                        callback_data=f"scc:{normalized}",
                        style=_BUTTON_STYLE_SUCCESS if not enabled else None,
                    )
                ],
                [InlineKeyboardButton("🔗 Открыть канал", url=f"https://t.me/{normalized}")],
                [_inline_button("🔙 К Telegram Channels", callback_data="srd:telegram_channels")],
            ]
        )

    def _load_source_posts(self, source_key: str, offset: int) -> tuple[int, list[dict[str, Any]]]:
        spec = source_catalog(settings).get(source_key)
        rows: list[dict[str, Any]] = []
        for status in ("review", "scheduled", "posted", "failed"):
            rows.extend(self._list_posts_rows(status=status, newest_first=True, limit=100))
        if source_key == "telegram_channels":
            filtered = [row for row in rows if extract_domain(str(row.get("source_url") or "")) == "t.me"]
        elif spec and spec.url:
            filtered = [row for row in rows if str(row.get("source_feed_url") or row.get("source_url") or "") == spec.url]
        elif spec and spec.domain:
            filtered = [row for row in rows if extract_domain(str(row.get("source_url") or "")) == spec.domain]
        else:
            filtered = rows
        total = len(filtered)
        return total, filtered[offset : offset + _POSTS_PAGE_SIZE]

    def _source_posts_text(self, source_key: str, total: int, rows: list[dict[str, Any]], offset: int) -> str:
        spec = source_catalog(settings).get(source_key)
        label = spec.name if spec else source_key
        if not rows:
            return f"Источник: {label}\n\nПостов по этому источнику пока нет."
        lines = [f"Источник: {label}", f"Всего постов: {total}", ""]
        for idx, row in enumerate(rows, start=offset + 1):
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            status_badge = _status_badge(str(row.get("status") or ""))
            publish_at = str(row.get("publish_at") or "")
            lines.append(f"{idx}. {status_badge} {title[:80]}")
            lines.append(f"   ⏰ {publish_at}")
        return "\n".join(lines)

    def _source_posts_keyboard(self, source_key: str, total: int, rows: list[dict[str, Any]], offset: int) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            status = str(row.get("status") or "scheduled")
            buttons.append([InlineKeyboardButton(f"{idx}. {_status_badge(status)} {title[:45]}", callback_data=f"pv:{post_id}:src_{source_key}:{offset}")])

        nav: list[InlineKeyboardButton] = []
        prev_offset = max(0, offset - _POSTS_PAGE_SIZE)
        next_offset = offset + _POSTS_PAGE_SIZE
        if offset > 0:
            nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"src:{source_key}:{prev_offset}"))
        if next_offset < total:
            nav.append(InlineKeyboardButton("➡️ Далее", callback_data=f"src:{source_key}:{next_offset}"))
        if nav:
            buttons.append(nav)
        buttons.append([_inline_button("🔙 К источникам", callback_data="sec:sources")])
        return InlineKeyboardMarkup(buttons)

    def _theme_stats(self) -> dict[str, int]:
        counts: dict[str, int] = {pillar: 0 for pillar in _PILLAR_LABELS}
        for status in ("review", "scheduled", "posted", "failed"):
            for row in self._list_posts_rows(status=status, newest_first=True, limit=100):
                title = str(row.get("title") or "")
                text = str(row.get("text") or "")
                pillar = normalize_rubric_to_pillar(row.get("rubric"), f"{title}\n{text}")
                counts[pillar] = counts.get(pillar, 0) + 1
        return counts

    def _themes_text(self, counts: dict[str, int]) -> str:
        lines = [
            "Тематики публикаций",
            "",
            "Канал узкоспециализированный: только AI в юриспруденции, автоматизация юрфункции, legal tech и связанные регуляторные изменения.",
            "",
        ]
        target_share = {
            "regulation": "30%",
            "case": "20%",
            "implementation": "30%",
            "tools": "15%",
            "market": "5%",
        }
        for pillar, label in _PILLAR_LABELS.items():
            rubric_labels = ", ".join(_rubric_label(item) for item in _PILLAR_RUBRICS.get(pillar, ()))
            lines.append(f"• {label}: {counts.get(pillar, 0)} пост(ов), целевая доля {target_share.get(pillar, 'n/a')}")
            if rubric_labels:
                lines.append(f"   Рубрики: {rubric_labels}")
        return "\n".join(lines)

    def _themes_keyboard(self, counts: dict[str, int]) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        pillars = list(_PILLAR_LABELS)
        for index in range(0, len(pillars), 2):
            chunk = pillars[index : index + 2]
            rows.append(
                [
                    _inline_button(
                        f"{_pillar_label(pillar)} ({counts.get(pillar, 0)})",
                        callback_data=f"th:{pillar}:0",
                    )
                    for pillar in chunk
                ]
            )
        rows.append([_inline_button("🔙 К разделам", callback_data="sections")])
        return InlineKeyboardMarkup(rows)

    def _load_theme_posts(self, pillar: str, offset: int) -> tuple[int, list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        for status in ("review", "scheduled", "posted", "failed"):
            rows.extend(self._list_posts_rows(status=status, newest_first=True, limit=100))
        filtered: list[dict[str, Any]] = []
        for row in rows:
            title = str(row.get("title") or "")
            text = str(row.get("text") or "")
            row_pillar = normalize_rubric_to_pillar(row.get("rubric"), f"{title}\n{text}")
            if row_pillar == pillar:
                filtered.append(row)
        total = len(filtered)
        return total, filtered[offset : offset + _POSTS_PAGE_SIZE]

    def _theme_posts_text(self, pillar: str, total: int, rows: list[dict[str, Any]], offset: int) -> str:
        label = _pillar_label(pillar)
        if not rows:
            return f"Тематика: {label}\n\nПостов пока нет."
        lines = [f"Тематика: {label}", f"Всего: {total}", ""]
        for idx, row in enumerate(rows, start=offset + 1):
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            rubric = _rubric_label(str(row.get("rubric") or ""))
            status_badge = _status_badge(str(row.get("status") or ""))
            lines.append(f"{idx}. {status_badge} {title[:82]}")
            lines.append(f"   Рубрика: {rubric}")
        return "\n".join(lines)

    def _theme_posts_keyboard(self, pillar: str, total: int, rows: list[dict[str, Any]], offset: int) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            status = str(row.get("status") or "scheduled")
            buttons.append([InlineKeyboardButton(f"{idx}. {_status_badge(status)} {title[:45]}", callback_data=f"pv:{post_id}:th_{pillar}:{offset}")])

        nav: list[InlineKeyboardButton] = []
        prev_offset = max(0, offset - _POSTS_PAGE_SIZE)
        next_offset = offset + _POSTS_PAGE_SIZE
        if offset > 0:
            nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"th:{pillar}:{prev_offset}"))
        if next_offset < total:
            nav.append(InlineKeyboardButton("➡️ Далее", callback_data=f"th:{pillar}:{next_offset}"))
        if nav:
            buttons.append(nav)
        buttons.append([_inline_button("🔙 К тематикам", callback_data="sec:themes")])
        return InlineKeyboardMarkup(buttons)

    def _generation_text(self, controls: dict[str, bool]) -> str:
        source_count = len(resolve_source_urls(settings, enabled_overrides=self._source_enabled_map()))
        slots = settings.news_weekday_slots.strip() or "не заданы"
        deep_days = settings.news_deep_days.strip() or "tue,thu"
        discussion_ready = bool((settings.news_discussion_chat_id or "").strip() or (settings.news_discussion_chat_username or "").strip())
        telegram_channel_count = len(self._telegram_channel_enabled_map())
        return (
            "Ручная генерация\n\n"
            f"Автогенерация: {'🟢' if controls.get('news.generate.enabled', True) else '🔴'}\n"
            f"Автопубликация: {'🟢' if controls.get('news.publish.enabled', True) else '🔴'}\n"
            f"Feedback guard: {'🟢' if controls.get('news.feedback.guard.enabled', True) else '🔴'}\n\n"
            f"Интервал автогенерации: {_humanize_interval(settings.news_generate_interval_seconds)}\n"
            f"Интервал автопубликации: {_humanize_interval(settings.news_publish_interval_seconds)}\n"
            f"Лимит генерации за цикл: {settings.news_generate_limit}\n"
            f"Источников RSS/search: {source_count}\n"
            f"Telegram-каналов: {telegram_channel_count}\n"
            f"Будничные слоты: {slots}\n"
            f"Дни глубоких разборов: {deep_days}\n\n"
            f"Комментарии/feedback: {'🟢 linked discussion group указана в контуре' if discussion_ready else '🟡 треды в Telegram могут работать, но для сбора feedback нужно указать linked discussion group в env'}\n\n"
            "Контур ограничен темами Legal AI, автоматизации юрфункции, legal tech и AI-регулирования.\n"
            "Общие AI-новости без связи с юридической функцией должны отсеиваться на этапе отбора.\n\n"
            "Ниже запускается подбор кандидатов. Затем открывается список драфтов: по каждому можно посмотреть исходную статью и текст поста, а потом сохранить его в review."
        )

    def _generation_keyboard(self, preview_count: int = 0) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                _inline_button("⚡ Подобрать 3", callback_data="gen:pick:3", style=_BUTTON_STYLE_SUCCESS),
                _inline_button("⚡ Подобрать 5", callback_data="gen:pick:5", style=_BUTTON_STYLE_SUCCESS),
            ],
            [
                _inline_button("⚡ Подобрать 10", callback_data="gen:pick:10", style=_BUTTON_STYLE_SUCCESS),
            ],
        ]
        if preview_count:
            rows.append(
                [
                    _inline_button(f"📄 Драфты ({preview_count})", callback_data="gen:list:0"),
                    _inline_button("🧹 Очистить", callback_data="gen:clear", style=_BUTTON_STYLE_DANGER),
                ]
            )
        rows.extend(
            [
                [
                    _inline_button("📰 Источники", callback_data="sec:sources"),
                    _inline_button("🧭 Тематики", callback_data="sec:themes"),
                ],
                [_inline_button("🔙 К разделам", callback_data="sections")],
            ]
        )
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def _generation_preview_card_text(preview: dict[str, Any], index: int, total: int) -> str:
        title = str(preview.get("title") or "Без заголовка")
        source_title = str(preview.get("source_title") or "Без заголовка")
        source_domain = str(preview.get("source_domain") or "—")
        source_summary = str(preview.get("source_summary") or "").strip()
        source_summary = source_summary[:900] + ("…" if len(source_summary) > 900 else "")
        text = _strip_html_markup(str(preview.get("text") or "").strip())
        if len(text) > 2100:
            text = text[:2100].rstrip() + "\n\n…"
        return "\n".join(
            [
                f"Драфт {index + 1} из {total}",
                "",
                f"Тематика: {_pillar_label(str(preview.get('pillar') or 'implementation'))}",
                f"Рубрика: {_rubric_label(str(preview.get('rubric') or ''))}",
                f"Формат: {preview.get('format_type') or 'standard'}",
                f"План публикации: {preview.get('publish_at') or '—'}",
                f"Источник: {source_domain}",
                f"Оригинальная статья: {source_title}",
                f"URL: {preview.get('source_url') or '—'}",
                "",
                "Краткое содержание статьи:",
                source_summary or "—",
                "",
                "Драфт поста:",
                text or "—",
            ]
        )

    def _generation_preview_card_keyboard(self, preview: dict[str, Any], index: int, total: int) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                _inline_button("✅ В review", callback_data=f"gen:save:{index}", style=_BUTTON_STYLE_SUCCESS),
                _inline_button("📄 К списку", callback_data="gen:list:0"),
            ],
            [_inline_button("🔗 Открыть статью", url=str(preview.get("source_url") or ""))],
        ]
        nav: list[InlineKeyboardButton] = []
        if index > 0:
            nav.append(_inline_button("⬅️ Пред.", callback_data=f"gen:view:{index - 1}"))
        if index + 1 < total:
            nav.append(_inline_button("➡️ След.", callback_data=f"gen:view:{index + 1}"))
        if nav:
            rows.append(nav)
        rows.append([_inline_button("🧹 Очистить список", callback_data="gen:clear", style=_BUTTON_STYLE_DANGER)])
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def _generation_preview_list_text(previews: list[dict[str, Any]], offset: int) -> str:
        if not previews:
            return "Подобранных драфтов пока нет."
        lines = ["Подобранные драфты", "", f"Всего: {len(previews)}", ""]
        for idx, preview in enumerate(previews[offset : offset + _POSTS_PAGE_SIZE], start=offset + 1):
            lines.append(
                f"{idx}. {str(preview.get('title') or 'Без заголовка')[:78]}"
            )
            lines.append(
                f"   {_pillar_label(str(preview.get('pillar') or 'implementation'))} | {preview.get('source_domain') or '—'}"
            )
        return "\n".join(lines)

    def _generation_preview_list_keyboard(self, previews: list[dict[str, Any]], offset: int) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        page = previews[offset : offset + _POSTS_PAGE_SIZE]
        for idx, preview in enumerate(page, start=offset):
            buttons.append(
                [
                    _inline_button(
                        f"{idx + 1}. {str(preview.get('title') or 'Без заголовка')[:40]}",
                        callback_data=f"gen:view:{idx}",
                    )
                ]
            )
        nav: list[InlineKeyboardButton] = []
        prev_offset = max(0, offset - _POSTS_PAGE_SIZE)
        next_offset = offset + _POSTS_PAGE_SIZE
        if offset > 0:
            nav.append(_inline_button("⬅️ Назад", callback_data=f"gen:list:{prev_offset}"))
        if next_offset < len(previews):
            nav.append(_inline_button("➡️ Далее", callback_data=f"gen:list:{next_offset}"))
        if nav:
            buttons.append(nav)
        buttons.append(
            [
                _inline_button("⚡ Подобрать еще", callback_data="sec:generate"),
                _inline_button("🧹 Очистить", callback_data="gen:clear", style=_BUTTON_STYLE_DANGER),
            ]
        )
        return InlineKeyboardMarkup(buttons)

    def _automation_keyboard(self, controls: list[dict[str, Any]]) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                _inline_button("🏠 Панель", callback_data="refresh"),
                _inline_button("📚 Разделы", callback_data="sections"),
            ],
            [
                _inline_button("✅ Включить всё", callback_data="all:1", style=_BUTTON_STYLE_SUCCESS),
                _inline_button("⛔ Отключить всё", callback_data="all:0", style=_BUTTON_STYLE_DANGER),
            ],
            [_inline_button("🧹 Сброс stale", callback_data="resetstale", style=_BUTTON_STYLE_DANGER)],
        ]
        for row in controls:
            key = str(row.get("key") or "")
            enabled = _is_enabled(row.get("enabled", True))
            next_value = "0" if enabled else "1"
            icon = "🟢" if enabled else "🔴"
            title = str(row.get("title") or key)
            button_text = f"{icon} {title}"
            rows.append(
                [
                    _inline_button(
                        button_text[:60],
                        callback_data=f"set:{key}:{next_value}",
                        style=_BUTTON_STYLE_SUCCESS if not enabled else _BUTTON_STYLE_DANGER,
                    )
                ]
            )
        return InlineKeyboardMarkup(rows)

    async def _queue_snapshot(self) -> tuple[dict[str, int], str]:
        now = datetime.now(timezone.utc)
        if self._queue_snapshot_cache is not None:
            loaded_at, payload = self._queue_snapshot_cache
            if (now - loaded_at).total_seconds() <= _QUEUE_CACHE_TTL_SECONDS:
                return payload

        counts: dict[str, int] = {}
        statuses = ("draft", "review", "scheduled", "publishing", "posted", "failed")
        async def _count_status(status: str) -> tuple[str, int]:
            try:
                rows = await asyncio.to_thread(
                    self._list_posts_rows,
                    status=status,
                    newest_first=True,
                    limit=100,
                )
                return status, len(rows)
            except Exception as exc:
                logger.warning("queue_status_fetch_failed", extra={"status": status, "error": str(exc)})
                return status, -1

        for status, count in await asyncio.gather(*(_count_status(status) for status in statuses)):
            counts[status] = count

        next_publish = "нет"
        try:
            rows = await asyncio.to_thread(
                self._list_posts_rows,
                status="scheduled",
                newest_first=False,
                limit=1,
            )
            if rows:
                next_publish = str(rows[0].get("publish_at") or "нет")
        except Exception as exc:
            logger.warning("next_publish_fetch_failed", extra={"error": str(exc)})

        payload = (counts, next_publish)
        self._queue_snapshot_cache = (now, payload)
        return payload

    async def _queue_text(self) -> str:
        counts, next_publish = await self._queue_snapshot()
        return (
            "Состояние очереди публикаций\n\n"
            f"draft: {counts['draft']}\n"
            f"review: {counts['review']}\n"
            f"scheduled: {counts['scheduled']}\n"
            f"publishing: {counts['publishing']}\n"
            f"posted (посл.100): {counts['posted']}\n"
            f"failed (посл.100): {counts['failed']}\n\n"
            f"Следующая публикация: {next_publish}"
        )

    async def _panel_text(self, controls: list[dict[str, Any]]) -> str:
        counts, next_publish = await self._queue_snapshot()
        control_map = {str(row.get("key") or ""): bool(row.get("enabled", True)) for row in controls}
        lines = [
            "Панель модератора Legal AI PRO",
            "",
            f"Автопилот: {'🟢' if control_map.get('news.generate.enabled', True) and control_map.get('news.publish.enabled', True) else '🔴'}",
            f"Сбор feedback: {'🟢' if control_map.get('news.feedback.collect.enabled', True) else '🔴'}",
            f"Защита по feedback: {'🟢' if control_map.get('news.feedback.guard.enabled', True) else '🔴'}",
            "",
            f"📝 Черновики: {counts.get('draft', -1)}",
            f"🟡 На проверке: {counts.get('review', -1)}",
            f"✅ Готовые: {counts.get('scheduled', -1)}",
            f"📤 Опубликованные: {counts.get('posted', -1)}",
            f"❌ Ошибки: {counts.get('failed', -1)}",
            "",
            f"Следующая публикация: {next_publish}",
            "",
            "Навигация: нижнее меню открывает основные разделы. Внутри рабочих экранов остаются только операционные кнопки.",
        ]
        return "\n".join(lines)

    def _load_posts(self, status: str, offset: int) -> tuple[int, list[dict[str, Any]]]:
        all_rows = self._list_posts_rows(status=status, newest_first=False, limit=100)
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

    def _ready_status_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        publish_at = self._publish_at_utc(row)
        if publish_at is None or publish_at <= datetime.now(timezone.utc):
            publish_at = _compute_quick_publish_at("h1")
        return {"status": "scheduled", "publish_at": publish_at.isoformat()}

    def _load_manual_queue(self, queue_filter: str, offset: int) -> tuple[int, list[dict[str, Any]], int, int]:
        all_rows = self._list_posts_rows(status="scheduled", newest_first=False, limit=100)
        now_utc = datetime.now(timezone.utc)
        due_rows = [row for row in all_rows if (publish_at := self._publish_at_utc(row)) and publish_at <= now_utc]
        filtered_rows = due_rows if queue_filter == "due" else all_rows
        total = len(filtered_rows)
        return total, filtered_rows[offset : offset + _POSTS_PAGE_SIZE], len(due_rows), len(all_rows)

    def _calendar_groups(self) -> list[tuple[str, list[dict[str, Any]]]]:
        rows = self._list_posts_rows(status="scheduled", newest_first=False, limit=100)
        tz = ZoneInfo(settings.tz_name)
        today_local = datetime.now(tz).date()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            publish_at = self._publish_at_utc(row)
            if publish_at is None:
                continue
            local_day = publish_at.astimezone(tz).date()
            if local_day < today_local:
                continue
            day_key = local_day.isoformat()
            grouped.setdefault(day_key, []).append(row)
        return sorted(grouped.items(), key=lambda item: item[0])

    def _overdue_scheduled_count(self) -> int:
        rows = self._list_posts_rows(status="scheduled", newest_first=False, limit=100)
        now_utc = datetime.now(timezone.utc)
        return sum(1 for row in rows if (publish_at := self._publish_at_utc(row)) and publish_at < now_utc)

    def _calendar_summary_text(self, groups: list[tuple[str, list[dict[str, Any]]]]) -> str:
        overdue_count = self._overdue_scheduled_count()
        if not groups:
            lines = ["Календарь публикаций", ""]
            if overdue_count:
                lines.append(f"Просроченных scheduled-постов: {overdue_count}")
                lines.append("Они не смешиваются с будущими датами. Откройте ручную очередь и переразложите их.")
                lines.append("")
            lines.append("На ближайшее время запланированных постов нет.")
            return "\n".join(lines)

        tz = ZoneInfo(settings.tz_name)
        now_local = datetime.now(tz).date()
        lines = ["Календарь публикаций", ""]
        if overdue_count:
            lines.append(f"Просроченных scheduled-постов: {overdue_count}")
            lines.append("Они вынесены из календаря текущих дат. Для работы с ними используйте ручную очередь.")
            lines.append("")
        for day_key, rows in groups[:7]:
            day_date = datetime.fromisoformat(day_key).date()
            if day_date == now_local:
                day_label = f"{day_key} (сегодня)"
            elif day_date == now_local + timedelta(days=1):
                day_label = f"{day_key} (завтра)"
            else:
                day_label = day_key
            first_time = self._publish_at_utc(rows[0])
            time_label = first_time.astimezone(tz).strftime("%H:%M") if first_time else "--:--"
            lines.append(f"• {day_label}: {len(rows)} пост(ов), первый слот {time_label}")
        return "\n".join(lines)

    def _calendar_summary_keyboard(self, groups: list[tuple[str, list[dict[str, Any]]]]) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        tz = ZoneInfo(settings.tz_name)
        now_local = datetime.now(tz).date()
        overdue_count = self._overdue_scheduled_count()
        row_buffer: list[InlineKeyboardButton] = []
        for day_key, rows in groups[:8]:
            day_date = datetime.fromisoformat(day_key).date()
            if day_date == now_local:
                day_label = "Сегодня"
            elif day_date == now_local + timedelta(days=1):
                day_label = "Завтра"
            else:
                day_label = day_date.strftime("%d.%m")
            row_buffer.append(
                InlineKeyboardButton(f"{day_label} ({len(rows)})", callback_data=f"cal:day:{day_key}")
            )
            if len(row_buffer) == 2:
                buttons.append(row_buffer)
                row_buffer = []
        if row_buffer:
            buttons.append(row_buffer)
        if overdue_count:
            buttons.append([InlineKeyboardButton(f"⚠️ Просрочено ({overdue_count})", callback_data="mq:due:0")])
        buttons.append([InlineKeyboardButton("🔄 Обновить календарь", callback_data="cal:summary")])
        buttons.append([InlineKeyboardButton("◀️ В панель", callback_data="refresh")])
        return InlineKeyboardMarkup(buttons)

    def _calendar_day_rows(self, day_key: str) -> list[dict[str, Any]]:
        for group_key, rows in self._calendar_groups():
            if group_key == day_key:
                return rows
        return []

    @staticmethod
    def _slots_for_day(day_value: date) -> list[tuple[int, int]]:
        weekday_slots = parse_schedule_slots(settings.news_weekday_slots)
        if day_value.weekday() == 5:
            saturday_raw = settings.news_saturday_slots.strip()
            return parse_schedule_slots(saturday_raw) if saturday_raw else weekday_slots
        if day_value.weekday() == 6:
            sunday_raw = settings.news_sunday_slots.strip()
            return parse_schedule_slots(sunday_raw) if sunday_raw else weekday_slots
        return weekday_slots

    def _next_publish_slots_after_day(self, day_key: str, count: int) -> list[datetime]:
        tz = ZoneInfo(settings.tz_name)
        start_day = datetime.fromisoformat(day_key).date() + timedelta(days=1)
        slots: list[datetime] = []
        for day_offset in range(0, 21):
            current_day = start_day + timedelta(days=day_offset)
            day_slots = self._slots_for_day(current_day)
            for hour, minute in day_slots:
                slots.append(datetime.combine(current_day, time(hour=hour, minute=minute), tzinfo=tz).astimezone(timezone.utc))
                if len(slots) >= count:
                    return slots
        return slots

    def _publish_slots_from_day(self, day_key: str, count: int, *, start_slot: tuple[int, int] | None = None) -> list[datetime]:
        tz = ZoneInfo(settings.tz_name)
        start_day = datetime.fromisoformat(day_key).date()
        slots: list[datetime] = []
        for day_offset in range(0, 21):
            current_day = start_day + timedelta(days=day_offset)
            day_slots = self._slots_for_day(current_day)
            for hour, minute in day_slots:
                if day_offset == 0 and start_slot is not None and (hour, minute) < start_slot:
                    continue
                slots.append(datetime.combine(current_day, time(hour=hour, minute=minute), tzinfo=tz).astimezone(timezone.utc))
                if len(slots) >= count:
                    return slots
        return slots

    @staticmethod
    def _move_to_next_day_same_time(publish_at_utc: datetime) -> datetime:
        tz = ZoneInfo(settings.tz_name)
        local_dt = publish_at_utc.astimezone(tz)
        next_day = (local_dt + timedelta(days=1)).date()
        target_local = datetime.combine(
            next_day,
            time(hour=local_dt.hour, minute=local_dt.minute),
            tzinfo=tz,
        )
        return target_local.astimezone(timezone.utc)

    def _bulk_move_day_to_tomorrow(self, day_key: str) -> int:
        rows = self._calendar_day_rows(day_key)
        moved = 0
        for row in rows:
            publish_at = self._publish_at_utc(row)
            if publish_at is None:
                continue
            self.client.patch_post(
                str(row.get("id")),
                {"publish_at": self._move_to_next_day_same_time(publish_at).isoformat()},
            ).raise_for_status()
            moved += 1
        if moved:
            self._invalidate_post_caches()
        return moved

    def _bulk_spread_day_to_next_slots(self, day_key: str) -> int:
        rows = self._calendar_day_rows(day_key)
        sorted_rows = sorted(
            rows,
            key=lambda row: self._publish_at_utc(row) or datetime.max.replace(tzinfo=timezone.utc),
        )
        slots = self._next_publish_slots_after_day(day_key, len(sorted_rows))
        moved = 0
        for row, publish_at in zip(sorted_rows, slots, strict=False):
            self.client.patch_post(
                str(row.get("id")),
                {"publish_at": publish_at.isoformat()},
            ).raise_for_status()
            moved += 1
        if moved:
            self._invalidate_post_caches()
        return moved

    def _bulk_reflow_day_from_slot(self, day_key: str, start_slot: tuple[int, int]) -> int:
        rows = self._calendar_day_rows(day_key)
        sorted_rows = sorted(
            rows,
            key=lambda row: self._publish_at_utc(row) or datetime.max.replace(tzinfo=timezone.utc),
        )
        slots = self._publish_slots_from_day(day_key, len(sorted_rows), start_slot=start_slot)
        moved = 0
        for row, publish_at in zip(sorted_rows, slots, strict=False):
            self.client.patch_post(
                str(row.get("id")),
                {"publish_at": publish_at.isoformat()},
            ).raise_for_status()
            moved += 1
        if moved:
            self._invalidate_post_caches()
        return moved

    def _calendar_day_text(self, day_key: str, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return f"Календарь публикаций\n\nНа {day_key} запланированных постов нет."

        tz = ZoneInfo(settings.tz_name)
        lines = [f"Календарь: {day_key}", f"Постов: {len(rows)}", ""]
        for index, row in enumerate(rows, start=1):
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            publish_at = self._publish_at_utc(row)
            time_label = publish_at.astimezone(tz).strftime("%H:%M") if publish_at else "--:--"
            lines.append(f"{index}. {time_label} {title[:82]}")
        return "\n".join(lines)

    def _calendar_day_keyboard(self, day_key: str, rows: list[dict[str, Any]]) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        if rows:
            buttons.append(
                [
                    InlineKeyboardButton("🚀 Опубликовать день", callback_data=f"cap:{day_key}"),
                    InlineKeyboardButton("📅 На завтра", callback_data=f"cas:tomorrow:{day_key}"),
                ]
            )
            buttons.append([InlineKeyboardButton("🧩 Следующие слоты", callback_data=f"cas:spread:{day_key}")])
            slot_buttons = [
                InlineKeyboardButton(
                    f"🕒 {hour:02d}:{minute:02d}",
                    callback_data=f"car:{day_key}:{_slot_token(hour, minute)}",
                )
                for hour, minute in self._slots_for_day(datetime.fromisoformat(day_key).date())
            ]
            if slot_buttons:
                buttons.append(slot_buttons[:3])
                if len(slot_buttons) > 3:
                    buttons.append(slot_buttons[3:6])
        for index, row in enumerate(rows, start=1):
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            buttons.append(
                [InlineKeyboardButton(f"{index}. {title[:45]}", callback_data=f"cav:{row.get('id')}:{day_key}")]
            )
        buttons.append(
            [
                InlineKeyboardButton("🔄 Обновить день", callback_data=f"cal:day:{day_key}"),
                InlineKeyboardButton("🗓 Все дни", callback_data="cal:summary"),
            ]
        )
        buttons.append([InlineKeyboardButton("◀️ В панель", callback_data="refresh")])
        return InlineKeyboardMarkup(buttons)

    def _day_publish_reason_keyboard(self, day_key: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data=f"cpn:{day_key}")]])

    def _day_publish_confirm_keyboard(self, day_key: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Подтвердить публикацию дня", callback_data=f"cpc:{day_key}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"cpn:{day_key}")],
            ]
        )

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
        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            status_badge = _status_badge(str(row.get("status") or status))
            buttons.append([InlineKeyboardButton(f"{idx}. {status_badge} {title[:45]}", callback_data=f"pv:{post_id}:{status}:{offset}")])

        if rows and status == "draft":
            buttons.append([InlineKeyboardButton("🟡 На проверку (все на странице)", callback_data=f"ba:review:{status}:{offset}")])
        if rows and status in ("review", "failed"):
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
        buttons.append([InlineKeyboardButton("🔙 К рабочим спискам", callback_data="sec:worklists")])
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
        buttons.append([InlineKeyboardButton("🔙 К рабочим спискам", callback_data="sec:worklists")])
        return InlineKeyboardMarkup(buttons)

    def _post_card_text(self, post: dict[str, Any]) -> str:
        title = str(post.get("title") or "Без заголовка")
        publish_at = str(post.get("publish_at") or "")
        status = str(post.get("status") or "")
        text = _strip_html_markup(str(post.get("text") or ""))
        format_type = str(post.get("format_type") or "n/a")
        cta_type = str(post.get("cta_type") or "n/a")
        rubric = str(post.get("rubric") or "")
        pillar = normalize_rubric_to_pillar(rubric, f"{title}\n{text}")
        telegram_message_id = post.get("telegram_message_id")
        posted_at = str(post.get("posted_at") or "")
        preview = text if len(text) <= 2500 else text[:2500] + "\n\n…"
        source_url = str(post.get("source_url") or "")
        feedback_snapshot = post.get("feedback_snapshot") or {}

        parts = [
            f"Пост: {title}",
            f"ID: {post.get('id')}",
            f"Статус: {status}",
            f"Публикация (план): {publish_at}",
            f"Формат: {format_type}",
            f"CTA: {cta_type}",
            f"Тематика: {_pillar_label(pillar)}",
            f"Рубрика: {_rubric_label(rubric)}",
        ]
        if telegram_message_id:
            parts.append(f"Telegram message_id: {telegram_message_id}")
        if posted_at:
            parts.append(f"Опубликован: {posted_at}")
        parts.extend(
            [
                "",
                self._format_feedback_snapshot(feedback_snapshot),
                "",
                preview,
            ]
        )
        if source_url:
            parts.extend(["", f"Источник: {source_url}"])
        return "\n".join(parts)

    def _post_card_keyboard(self, post_id: str, status: str, offset: int) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        if status != "posted":
            rows.extend(
                [
                    [
                        InlineKeyboardButton("⏱ +1ч", callback_data=f"pt:{post_id}:{status}:{offset}:h1"),
                        InlineKeyboardButton("🌙 19:00", callback_data=f"pt:{post_id}:{status}:{offset}:e19"),
                    ],
                    [InlineKeyboardButton("🌤 Завтра 10:00", callback_data=f"pt:{post_id}:{status}:{offset}:t10")],
                    [InlineKeyboardButton("🚀 Опубликовать сейчас", callback_data=f"ppc:{post_id}:{status}:{offset}")],
                    [InlineKeyboardButton("✍️ Редактировать вручную", callback_data=f"pm:{post_id}:{status}:{offset}")],
                    [InlineKeyboardButton("🤖 Редактировать через LLM", callback_data=f"pa:{post_id}:{status}:{offset}")],
                    [InlineKeyboardButton("🗑 Нерелевантно / удалить", callback_data=f"pdd:{post_id}:{status}:{offset}", style=_BUTTON_STYLE_DANGER)],
                ]
            )
        else:
            rows.append([InlineKeyboardButton("🔄 Обновить карточку", callback_data=f"pv:{post_id}:{status}:{offset}")])
        if status == "draft":
            rows.append([InlineKeyboardButton("🟡 На проверку", callback_data=f"rr:{post_id}:{status}:{offset}")])
        if status in ("review", "failed"):
            rows.append([InlineKeyboardButton("✅ В готовые", callback_data=f"pr:{post_id}:{status}:{offset}")])
        if _is_calendar_context(status):
            rows.append([InlineKeyboardButton("🔙 К календарю", callback_data=f"cal:day:{_calendar_date_from_context(status)}")])
        elif _is_theme_context(status):
            rows.append([InlineKeyboardButton("🔙 К тематике", callback_data=f"th:{_theme_from_context(status)}:{offset}")])
        elif _is_source_context(status):
            rows.append([InlineKeyboardButton("🔙 К источнику", callback_data=f"src:{_source_from_context(status)}:{offset}")])
        elif _is_manual_queue_context(status):
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

    def _delete_reason_keyboard(self, post_id: str, status: str, offset: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data=f"pdn:{post_id}:{status}:{offset}")]])

    def _delete_confirm_keyboard(self, post_id: str, status: str, offset: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🗑 Удалить пост", callback_data=f"pdy:{post_id}:{status}:{offset}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"pdn:{post_id}:{status}:{offset}")],
            ]
        )

    def _batch_publish_reason_keyboard(self, queue_filter: str, offset: int, mode: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data=f"mbn:{queue_filter}:{offset}:{mode}")]])

    def _batch_publish_confirm_keyboard(self, queue_filter: str, offset: int, mode: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Подтвердить пакетную публикацию", callback_data=f"mbc:{queue_filter}:{offset}:{mode}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"mbn:{queue_filter}:{offset}:{mode}")],
            ]
        )

    def _create_start_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✍️ Написать вручную", callback_data="cn:manual")],
                [InlineKeyboardButton("🤖 Сгенерировать по тезисам", callback_data="cn:ai")],
                [InlineKeyboardButton("❌ Отменить", callback_data="cn:cancel")],
            ]
        )

    def _create_draft_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✏️ Заголовок", callback_data="ce:title"),
                    InlineKeyboardButton("📝 Текст", callback_data="ce:text"),
                ],
                [InlineKeyboardButton("🤖 Доработать через LLM", callback_data="ce:ai")],
                [InlineKeyboardButton("🆕 Сохранить в черновики", callback_data="cs:draft")],
                [InlineKeyboardButton("🟡 Отправить на проверку", callback_data="cs:review")],
                [
                    InlineKeyboardButton("✅ +1ч", callback_data="cs:scheduled:h1"),
                    InlineKeyboardButton("🌙 19:00", callback_data="cs:scheduled:e19"),
                ],
                [InlineKeyboardButton("🌤 Завтра 10:00", callback_data="cs:scheduled:t10")],
                [
                    InlineKeyboardButton("🧹 Новый с нуля", callback_data="cn:start"),
                    InlineKeyboardButton("❌ Закрыть", callback_data="cn:cancel"),
                ],
            ]
        )

    async def _show_create_start(self, update: Update) -> None:
        context_text = (
            "Создание нового поста\n\n"
            "Выберите режим:\n"
            "✍️ вручную — сами задаете текст поста\n"
            "🤖 через LLM — отправляете тезисы, бот собирает черновик\n\n"
            "После этого сможете сохранить материал в черновики или сразу в готовые с выбранным временем."
        )
        await update.effective_message.reply_text(context_text, reply_markup=self._create_start_keyboard())

    async def _show_create_draft(self, message, draft: dict[str, Any]) -> None:
        await message.reply_text(
            self._render_create_preview(draft),
            reply_markup=self._create_draft_keyboard(),
        )

    def _render_create_preview(self, draft: dict[str, Any]) -> str:
        title = str(draft.get("title") or "Без заголовка")
        text = str(draft.get("text") or "")
        preview = text if len(text) <= 2500 else text[:2500] + "\n\n…"
        mode = str(draft.get("mode") or "manual")
        mode_label = "LLM" if mode == "ai" else "ручной"
        brief = str(draft.get("brief") or "").strip()
        return (
            "Черновик нового поста\n\n"
            f"Заголовок: {title}\n"
            f"Режим: {mode_label}\n"
            f"Длина текста: {len(text)} символов\n"
            + (f"Тезисы: {brief[:220]}\n" if brief else "")
            + "\n"
            f"{preview}\n\n"
            "Можно доработать черновик или сразу сохранить:"
        )

    def _create_post_payload(
        self,
        draft: dict[str, Any],
        *,
        status: str,
        publish_at: datetime,
    ) -> dict[str, Any]:
        return {
            "channel_id": settings.telegram_channel_id or None,
            "channel_username": settings.telegram_channel_username or None,
            "title": str(draft.get("title") or "").strip() or None,
            "text": str(draft.get("text") or "").strip(),
            "publish_at": publish_at.isoformat(),
            "status": status,
            "format_type": "manual" if str(draft.get("mode") or "manual") == "manual" else "operator_ai",
            "cta_type": "manual",
            "rubric": "manual",
        }

    def _run_generate_now(self, limit: int) -> tuple[int, str]:
        command = [sys.executable, "-m", "news.generate", "--limit", str(limit)]
        result = subprocess.run(
            command,
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        tail_parts = [part.strip() for part in (result.stdout, result.stderr) if part.strip()]
        tail_text = "\n".join(tail_parts)[-1800:].strip()
        return result.returncode, tail_text

    async def _send_to_telegram(self, context: ContextTypes.DEFAULT_TYPE, text: str, media_urls: list[str] | None) -> int:
        chat_id = settings.telegram_channel_id or settings.telegram_channel_username
        if not chat_id:
            raise RuntimeError("TELEGRAM_CHANNEL_ID or TELEGRAM_CHANNEL_USERNAME is required")

        if media_urls:
            photo_value = media_urls[0]
            if photo_value.startswith("tg://"):
                photo_value = photo_value.replace("tg://", "", 1)
            caption = (text or "")[:1020]
            remainder = (text or "")[1020:].strip()
            message = await context.bot.send_photo(chat_id=chat_id, photo=photo_value, caption=caption, parse_mode="HTML")
            for part in _split_text_for_telegram(remainder):
                await context.bot.send_message(chat_id=chat_id, text=part, parse_mode="HTML", disable_web_page_preview=True)
            return int(message.message_id)

        primary_message_id = 0
        for part in _split_text_for_telegram(text):
            message = await context.bot.send_message(chat_id=chat_id, text=part, parse_mode="HTML", disable_web_page_preview=True)
            if primary_message_id == 0:
                primary_message_id = int(message.message_id)
        return primary_message_id

    async def _publish_now(self, context: ContextTypes.DEFAULT_TYPE, post_id: str, reason: str | None = None) -> None:
        post = self._get_post(post_id)
        operator_note = _normalize_operator_note(reason or "")
        self.client.patch_post(post_id, {"status": "publishing", "last_error": None}).raise_for_status()
        self._invalidate_post_caches()
        try:
            message_id = await self._send_to_telegram(context, str(post.get("text") or ""), post.get("media_urls"))
            self.client.patch_post(
                post_id,
                {
                    "status": "posted",
                    "last_error": None,
                    "telegram_message_id": message_id or None,
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                },
            ).raise_for_status()
            self._invalidate_post_caches()
            logger.info("manual_publish_success", extra={"post_id": post_id, "operator_note": operator_note})
        except Exception as exc:
            self.client.patch_post(post_id, {"status": "failed", "last_error": str(exc)[:500]}).raise_for_status()
            self._invalidate_post_caches()
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

    def _draft_post_with_llm(self, title: str, brief: str) -> str:
        client = self._get_openai_client()
        system_prompt = (
            "Ты редактор Telegram-канала Legal AI PRO. "
            "Собери профессиональный, плотный по смыслу пост на русском языке. "
            "Тон: деловой, уверенный, без воды и кликбейта. "
            "Не выдумывай факты, которых нет в тезисах пользователя. "
            "Верни только итоговый текст поста без JSON и без markdown-блоков."
        )
        completion_kwargs: dict[str, Any]
        if self._use_max_tokens_param:
            completion_kwargs = {"max_tokens": 1500}
        else:
            completion_kwargs = {"max_completion_tokens": 1500}

        response = client.chat.completions.create(
            model=settings.news_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Заголовок: {title}\n\n"
                        f"Тезисы / вводные:\n{brief}\n\n"
                        "Собери готовый Telegram-пост для канала об AI и автоматизации юридической функции."
                    ),
                },
            ],
            temperature=0.35,
            **completion_kwargs,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("LLM вернул пустой черновик")
        return content

    async def _collect_comment_feedback(self, message: Message) -> None:
        if not self._feedback_collection_enabled():
            return
        if message.chat.type not in {"supergroup", "group"}:
            return
        if not self._discussion_chat_matches(message):
            return

        channel_message_id = self._extract_channel_post_message_id(message.reply_to_message)
        if channel_message_id is None:
            return

        response = self.client.lookup_post_by_telegram_message(
            channel_message_id,
            channel_id=settings.telegram_channel_id or None,
            channel_username=settings.telegram_channel_username or None,
        )
        if response.status_code == 404:
            return
        response.raise_for_status()
        post = response.json()

        text = (message.text or message.caption or "").strip()
        signal_value, sentiment = classify_comment_signal(text)
        payload = {
            "sentiment": sentiment,
            "excerpt": " ".join(text.split())[:240],
        }
        feedback_response = self.client.create_post_feedback(
            str(post["id"]),
            {
                "source": "comment",
                "signal_key": sentiment,
                "signal_value": signal_value,
                "text": text,
                "telegram_chat_id": str(message.chat.id),
                "telegram_message_id": int(message.message_id),
                "telegram_user_id": getattr(getattr(message, "from_user", None), "id", None),
                "actor_name": getattr(getattr(message, "from_user", None), "full_name", None),
                "payload": payload,
            },
        )
        feedback_response.raise_for_status()
        logger.info(
            "news_feedback_comment_collected",
            extra={"post_id": post["id"], "message_id": message.message_id, "sentiment": sentiment},
        )

    async def on_feedback_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        message = update.effective_message
        if message is None:
            return
        try:
            await self._collect_comment_feedback(message)
        except Exception as exc:
            logger.exception("news_feedback_comment_failed", extra={"error": str(exc)})

    async def on_feedback_reaction_count(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not self._feedback_collection_enabled():
            return

        payload_update: MessageReactionCountUpdated | None = update.message_reaction_count
        if payload_update is None:
            return

        try:
            response = self.client.lookup_post_by_telegram_message(
                int(payload_update.message_id),
                channel_id=settings.telegram_channel_id or None,
                channel_username=settings.telegram_channel_username or None,
            )
            if response.status_code == 404:
                return
            response.raise_for_status()
            post = response.json()

            reaction_summary = summarize_reaction_counts(list(payload_update.reactions or ()))
            feedback_response = self.client.create_post_feedback(
                str(post["id"]),
                {
                    "source": "reaction_count",
                    "signal_key": "reaction_count",
                    "signal_value": 0,
                    "telegram_chat_id": str(payload_update.chat.id),
                    "telegram_message_id": int(payload_update.message_id),
                    "payload": reaction_summary,
                },
            )
            feedback_response.raise_for_status()
            logger.info(
                "news_feedback_reaction_count_collected",
                extra={"post_id": post["id"], "message_id": payload_update.message_id},
            )
        except Exception as exc:
            logger.exception("news_feedback_reaction_failed", extra={"error": str(exc)})

    async def _show_panel_message(self, update: Update, *, intro: bool = False) -> None:
        controls = self._load_controls(force_refresh=True)
        text = await self._panel_text(controls)
        if intro:
            text = (
                "Админ-панель контент-бота Legal AI PRO\n\n"
                "Это рабочий пульт редактора: автопилот, очереди постов, ручная публикация и контроль feedback.\n\n"
                + text
            )
        await update.effective_message.reply_text(
            text,
            reply_markup=_main_menu_markup(),
        )

    async def _show_sections_message(self, update: Update) -> None:
        counts, next_publish = await self._queue_snapshot()
        await update.effective_message.reply_text(
            self._sections_text(counts, next_publish),
            reply_markup=self._sections_keyboard(counts),
        )

    async def _show_worklists_message(self, update: Update) -> None:
        counts, next_publish = await self._queue_snapshot()
        await update.effective_message.reply_text(
            self._worklists_text(counts, next_publish),
            reply_markup=self._worklists_keyboard(counts),
        )

    async def _show_sources_message(self, update: Update) -> None:
        await update.effective_message.reply_text(
            self._sources_text(),
            reply_markup=self._sources_keyboard(),
        )

    async def _show_themes_message(self, update: Update) -> None:
        counts = self._theme_stats()
        await update.effective_message.reply_text(
            self._themes_text(counts),
            reply_markup=self._themes_keyboard(counts),
        )

    async def _show_generation_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        controls = self._controls_map(force_refresh=True)
        previews = context.user_data.get(_STATE_GENERATION_PREVIEWS) or []
        await update.effective_message.reply_text(
            self._generation_text(controls),
            reply_markup=self._generation_keyboard(len(previews)),
        )

    async def _show_posts_status(self, update: Update, status: str, offset: int = 0) -> None:
        total, rows = self._load_posts(status=status, offset=offset)
        await update.effective_message.reply_text(
            self._posts_text(total, rows, offset, status),
            reply_markup=self._posts_keyboard(total, rows, offset, status),
        )

    async def _show_manual_queue(self, update: Update, queue_filter: str = "due", offset: int = 0) -> None:
        total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
        await update.effective_message.reply_text(
            self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
            reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
        )

    async def _show_calendar_summary(self, update: Update) -> None:
        groups = self._calendar_groups()
        await update.effective_message.reply_text(
            self._calendar_summary_text(groups),
            reply_markup=self._calendar_summary_keyboard(groups),
        )

    async def _show_calendar_day(self, update: Update, day_key: str) -> None:
        rows = self._calendar_day_rows(day_key)
        await update.effective_message.reply_text(
            self._calendar_day_text(day_key, rows),
            reply_markup=self._calendar_day_keyboard(day_key, rows),
        )

    async def _post_init(self, app: Application) -> None:
        await app.bot.set_my_commands(
            [
                BotCommand("start", "Открыть панель"),
                BotCommand("admin", "Главная панель"),
                BotCommand("sections", "Рабочие разделы"),
                BotCommand("sources", "Источники новостей"),
                BotCommand("themes", "Тематики контента"),
                BotCommand("newpost", "Создать пост"),
                BotCommand("generate_now", "Принудительная генерация"),
                BotCommand("calendar", "Календарь публикаций"),
                BotCommand("help", "Помощь"),
            ]
        )

    async def cmd_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            await self._show_panel_message(update, intro=False)
        except Exception as exc:
            logger.exception("admin_panel_load_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(f"Ошибка загрузки панели: {exc}", reply_markup=_main_menu_markup())

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            await self._show_panel_message(update, intro=True)
        except Exception as exc:
            logger.exception("admin_start_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(f"Ошибка запуска панели: {exc}", reply_markup=_main_menu_markup())

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        text = await self._queue_text()
        await update.effective_message.reply_text(text, reply_markup=_main_menu_markup())

    async def cmd_calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            await self._show_calendar_summary(update)
        except Exception as exc:
            logger.exception("calendar_load_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(
                f"Ошибка загрузки календаря: {exc}",
                reply_markup=_main_menu_markup(),
            )

    async def cmd_new_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        context.user_data.pop(_STATE_PENDING_EDIT, None)
        context.user_data.pop(_STATE_DRAFT_EDIT, None)
        context.user_data.pop(_STATE_PENDING_PUBLISH_REASON, None)
        context.user_data.pop(_STATE_DRAFT_PUBLISH, None)
        context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
        context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
        context.user_data.pop(_STATE_PENDING_CREATE, None)
        draft = context.user_data.get(_STATE_DRAFT_CREATE)
        if draft:
            await self._show_create_draft(update.effective_message, draft)
            return
        context.user_data.pop(_STATE_DRAFT_CREATE, None)
        await self._show_create_start(update)

    async def cmd_sections(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            await self._show_sections_message(update)
        except Exception as exc:
            logger.exception("sections_list_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(
                f"Ошибка загрузки разделов: {exc}",
                reply_markup=_main_menu_markup(),
            )

    async def cmd_sources(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        await self._show_sources_message(update)

    async def cmd_themes(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        await self._show_themes_message(update)

    async def cmd_generate_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        await self._show_generation_message(update, context)

    async def cmd_posts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            await self._show_posts_status(update, status="scheduled", offset=0)
        except Exception as exc:
            logger.exception("posts_list_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(f"Ошибка загрузки постов: {exc}", reply_markup=_main_menu_markup())

    async def cmd_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            await self._show_manual_queue(update, queue_filter="due", offset=0)
        except Exception as exc:
            logger.exception("manual_queue_load_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(f"Ошибка загрузки ручной очереди: {exc}", reply_markup=_main_menu_markup())

    async def cmd_workers(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            response = self.admin_client.workers_status()
            response.raise_for_status()
            await update.effective_message.reply_text(
                _format_workers_status(response.json()),
                reply_markup=_main_menu_markup(),
            )
        except Exception as exc:
            if _is_scope_error(exc):
                await update.effective_message.reply_text(
                    "Для команды /workers нужен ключ со scope `admin` или `worker`.\n"
                    "Добавьте `API_KEY_ADMIN` в .env для admin-бота.",
                    reply_markup=_main_menu_markup(),
                )
            else:
                await update.effective_message.reply_text(
                    f"Ошибка получения статуса воркеров: {exc}",
                    reply_markup=_main_menu_markup(),
                )

    async def cmd_cancel_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_admin(update):
            return
        context.user_data.pop(_STATE_PENDING_EDIT, None)
        context.user_data.pop(_STATE_DRAFT_EDIT, None)
        context.user_data.pop(_STATE_PENDING_PUBLISH_REASON, None)
        context.user_data.pop(_STATE_DRAFT_PUBLISH, None)
        context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
        context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
        context.user_data.pop(_STATE_PENDING_CREATE, None)
        context.user_data.pop(_STATE_DRAFT_CREATE, None)
        context.user_data.pop(_STATE_PENDING_DAY_PUBLISH_REASON, None)
        context.user_data.pop(_STATE_DRAFT_DAY_PUBLISH, None)
        await update.effective_message.reply_text(
            "Режимы редактирования/создания/публикации отменены.",
            reply_markup=_main_menu_markup(),
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        await update.effective_message.reply_text(
            "Разделы админ-бота:\n"
            "🏠 Панель — главный экран и быстрые переходы\n"
            "➕ Создать — мастер нового поста вручную или через LLM\n"
            "🗓 Календарь — ближайшие публикации по дням\n"
            "📚 Разделы — списки, тематики, источники и генерация\n"
            "🤖 Автоматизация — тумблеры автогенерации, публикации и feedback\n"
            "🚀 Очередь / 👷 Воркеры / 📊 Сводка — внутри панели и подменю\n\n"
            "Fallback-команды:\n"
            "/start, /admin, /sections, /sources, /themes, /newpost, /generate_now, /calendar, /status, /posts, /queue, /workers, /cancel_edit, /help",
            reply_markup=_main_menu_markup(),
        )

    async def cb_calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return

        query = update.callback_query
        await query.answer()
        data = query.data or ""

        try:
            if data == "cal:summary":
                groups = self._calendar_groups()
                await self._safe_edit_message_text(
                    query,
                    self._calendar_summary_text(groups),
                    reply_markup=self._calendar_summary_keyboard(groups),
                )
                return

            if data.startswith("cal:day:"):
                day_key = data.split(":", maxsplit=2)[2]
                rows = self._calendar_day_rows(day_key)
                await self._safe_edit_message_text(
                    query,
                    self._calendar_day_text(day_key, rows),
                    reply_markup=self._calendar_day_keyboard(day_key, rows),
                )
                return

            if data.startswith("cap:"):
                day_key = data.split(":", maxsplit=1)[1]
                rows = self._calendar_day_rows(day_key)
                post_ids = [str(row.get("id")) for row in rows if row.get("id")]
                if not post_ids:
                    await self._safe_edit_message_text(
                        query,
                        self._calendar_day_text(day_key, rows),
                        reply_markup=self._calendar_day_keyboard(day_key, rows),
                    )
                    return
                context.user_data[_STATE_PENDING_DAY_PUBLISH_REASON] = {
                    "day_key": day_key,
                    "post_ids": post_ids,
                }
                context.user_data.pop(_STATE_DRAFT_DAY_PUBLISH, None)
                await self._safe_edit_message_text(
                    query,
                    "Пакетная публикация дня: шаг 1 из 2\n\n"
                    f"Дата: {day_key}\n"
                    f"Постов к публикации: {len(post_ids)}\n\n"
                    "Напишите одной фразой причину ручной публикации этого дня.",
                    reply_markup=self._day_publish_reason_keyboard(day_key),
                )
                return

            if data.startswith("cpc:"):
                day_key = data.split(":", maxsplit=1)[1]
                draft = context.user_data.get(_STATE_DRAFT_DAY_PUBLISH)
                if not draft or str(draft.get("day_key")) != day_key:
                    await query.message.reply_text("Причина пакетной публикации дня не найдена. Запустите действие заново.")
                    return
                post_ids = [str(item) for item in draft.get("post_ids", []) if item]
                reason = _normalize_operator_note(str(draft.get("reason") or ""))
                success_count = 0
                failed: list[str] = []
                for post_id in post_ids:
                    try:
                        await self._publish_now(context, post_id, reason)
                        success_count += 1
                    except Exception:
                        failed.append(post_id)
                context.user_data.pop(_STATE_PENDING_DAY_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_DAY_PUBLISH, None)
                rows = self._calendar_day_rows(day_key)
                result_lines = [
                    "Публикация дня завершена.",
                    f"Причина: {reason}",
                    f"Успешно: {success_count}",
                    f"С ошибкой: {len(failed)}",
                    "",
                ]
                if failed:
                    result_lines.append("ID с ошибками: " + ", ".join(failed[:5]))
                    result_lines.append("")
                await self._safe_edit_message_text(
                    query,
                    "\n".join(result_lines) + self._calendar_day_text(day_key, rows),
                    reply_markup=self._calendar_day_keyboard(day_key, rows),
                )
                return

            if data.startswith("cpn:"):
                day_key = data.split(":", maxsplit=1)[1]
                context.user_data.pop(_STATE_PENDING_DAY_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_DAY_PUBLISH, None)
                rows = self._calendar_day_rows(day_key)
                await self._safe_edit_message_text(
                    query,
                    "Публикация дня отменена.\n\n" + self._calendar_day_text(day_key, rows),
                    reply_markup=self._calendar_day_keyboard(day_key, rows),
                )
                return

            if data.startswith("cas:"):
                _, action, day_key = data.split(":", maxsplit=2)
                if action == "tomorrow":
                    moved = self._bulk_move_day_to_tomorrow(day_key)
                    target_day = (datetime.fromisoformat(day_key).date() + timedelta(days=1)).isoformat()
                    rows = self._calendar_day_rows(target_day)
                    await self._safe_edit_message_text(
                        query,
                        f"Перенесено на завтра: {moved} пост(ов).\n\n" + self._calendar_day_text(target_day, rows),
                        reply_markup=self._calendar_day_keyboard(target_day, rows),
                    )
                    return
                if action == "spread":
                    moved = self._bulk_spread_day_to_next_slots(day_key)
                    groups = self._calendar_groups()
                    await self._safe_edit_message_text(
                        query,
                        f"День перераспределен по следующим слотам: {moved} пост(ов).\n\n"
                        + self._calendar_summary_text(groups),
                        reply_markup=self._calendar_summary_keyboard(groups),
                    )
                    return

            if data.startswith("car:"):
                _, day_key, slot_token = data.split(":", maxsplit=2)
                start_slot = _slot_from_token(slot_token)
                moved = self._bulk_reflow_day_from_slot(day_key, start_slot)
                groups = self._calendar_groups()
                await self._safe_edit_message_text(
                    query,
                    f"День переразложен по слотам от {start_slot[0]:02d}:{start_slot[1]:02d}: {moved} пост(ов).\n\n"
                    + self._calendar_summary_text(groups),
                    reply_markup=self._calendar_summary_keyboard(groups),
                )
                return

            if data.startswith("cav:"):
                _, post_id, day_key = data.split(":", maxsplit=2)
                post = self._get_post(post_id)
                await self._safe_edit_message_text(
                    query,
                    self._post_card_text(post),
                    reply_markup=self._post_card_keyboard(post_id, _calendar_context(day_key), 0),
                )
                return
        except Exception as exc:
            logger.exception("calendar_callback_failed", extra={"callback_data": data, "error": str(exc)})
            await query.message.reply_text(f"Ошибка календаря: {exc}")

    async def cb_create(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_admin(update):
            return

        query = update.callback_query
        await query.answer()
        data = query.data or ""

        try:
            if data == "cn:start":
                context.user_data.pop(_STATE_PENDING_CREATE, None)
                context.user_data.pop(_STATE_DRAFT_CREATE, None)
                await self._safe_edit_message_text(
                    query,
                    "Создание нового поста\n\n"
                    "Выберите режим создания материала.",
                    reply_markup=self._create_start_keyboard(),
                )
                return

            if data == "cn:manual":
                context.user_data[_STATE_PENDING_CREATE] = {"mode": "manual", "step": "title"}
                context.user_data.pop(_STATE_DRAFT_CREATE, None)
                await self._safe_edit_message_text(
                    query,
                    "Новый пост: шаг 1 из 2\n\n"
                    "Пришлите заголовок или тему поста одним сообщением.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("❌ Отменить", callback_data="cn:cancel")]]
                    ),
                )
                return

            if data == "cn:ai":
                context.user_data[_STATE_PENDING_CREATE] = {"mode": "ai", "step": "title"}
                context.user_data.pop(_STATE_DRAFT_CREATE, None)
                await self._safe_edit_message_text(
                    query,
                    "Новый пост через LLM: шаг 1 из 2\n\n"
                    "Пришлите заголовок или тему поста одним сообщением.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("❌ Отменить", callback_data="cn:cancel")]]
                    ),
                )
                return

            if data == "cn:cancel":
                context.user_data.pop(_STATE_PENDING_CREATE, None)
                context.user_data.pop(_STATE_DRAFT_CREATE, None)
                controls = self._load_controls(force_refresh=True)
                await self._safe_edit_message_text(
                    query,
                    await self._panel_text(controls),
                    reply_markup=self._panel_keyboard(),
                )
                return

            if data.startswith("ce:"):
                draft = context.user_data.get(_STATE_DRAFT_CREATE)
                if not draft:
                    await query.message.reply_text("Активный черновик не найден. Запустите создание поста заново.")
                    return

                _, action = data.split(":", maxsplit=1)
                if action == "title":
                    context.user_data[_STATE_PENDING_CREATE] = {
                        "mode": str(draft.get("mode") or "manual"),
                        "step": "edit_title",
                    }
                    await self._safe_edit_message_text(
                        query,
                        "Редактирование заголовка\n\nПришлите новый заголовок одним сообщением.",
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("❌ Отменить", callback_data="cd:view")]]
                        ),
                    )
                    return
                if action == "text":
                    context.user_data[_STATE_PENDING_CREATE] = {
                        "mode": str(draft.get("mode") or "manual"),
                        "step": "edit_text",
                    }
                    await self._safe_edit_message_text(
                        query,
                        "Редактирование текста\n\nПришлите новый полный текст поста одним сообщением.",
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("❌ Отменить", callback_data="cd:view")]]
                        ),
                    )
                    return
                if action == "ai":
                    context.user_data[_STATE_PENDING_CREATE] = {
                        "mode": str(draft.get("mode") or "manual"),
                        "step": "edit_ai",
                    }
                    await self._safe_edit_message_text(
                        query,
                        "LLM-доработка черновика\n\nНапишите инструкцию для доработки текущего текста.\n"
                        "Пример: «Сделай жестче вступление, сократи середину и усили вывод».",
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("❌ Отменить", callback_data="cd:view")]]
                        ),
                    )
                    return

            if data == "cd:view":
                draft = context.user_data.get(_STATE_DRAFT_CREATE)
                if not draft:
                    await self._safe_edit_message_text(
                        query,
                        "Активного черновика нет.\n\nВыберите режим создания материала.",
                        reply_markup=self._create_start_keyboard(),
                    )
                    return
                context.user_data.pop(_STATE_PENDING_CREATE, None)
                await self._safe_edit_message_text(
                    query,
                    self._render_create_preview(draft),
                    reply_markup=self._create_draft_keyboard(),
                )
                return

            if data in {"cs:draft", "cs:review"} or data.startswith("cs:scheduled:"):
                draft = context.user_data.get(_STATE_DRAFT_CREATE)
                if not draft:
                    await query.message.reply_text("Черновик нового поста не найден. Запустите создание заново.")
                    return

                if data == "cs:draft":
                    status = "draft"
                    publish_at = datetime.now(timezone.utc)
                elif data == "cs:review":
                    status = "review"
                    publish_at = datetime.now(timezone.utc)
                else:
                    _, status, slot = data.split(":", maxsplit=2)
                    publish_at = _compute_quick_publish_at(slot)

                payload = self._create_post_payload(draft, status=status, publish_at=publish_at)
                response = self.client.create_scheduled_post(payload)
                response.raise_for_status()
                self._invalidate_post_caches()
                post = response.json()

                context.user_data.pop(_STATE_PENDING_CREATE, None)
                context.user_data.pop(_STATE_DRAFT_CREATE, None)

                if status == "draft":
                    publish_label = "черновики"
                elif status == "review":
                    publish_label = "проверку"
                else:
                    publish_label = f"готовые ({publish_at.isoformat()})"
                await self._safe_edit_message_text(
                    query,
                    f"Новый пост сохранен в {publish_label}.\n\n" + self._post_card_text(post),
                    reply_markup=self._post_card_keyboard(str(post["id"]), str(post["status"]), 0),
                )
                return
        except Exception as exc:
            logger.exception("create_callback_failed", extra={"callback_data": data, "error": str(exc)})
            await query.message.reply_text(f"Ошибка создания поста: {exc}")

    async def cb_controls(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        query = update.callback_query
        await query.answer()
        data = query.data or ""

        try:
            if data == "refresh":
                controls = self._load_controls(force_refresh=True)
                await self._safe_edit_message_text(
                    query,
                    await self._panel_text(controls),
                )
                return

            if data == "sections":
                counts, next_publish = await self._queue_snapshot()
                await self._safe_edit_message_text(
                    query,
                    self._sections_text(counts, next_publish),
                    reply_markup=self._sections_keyboard(counts),
                )
                return

            if data == "sec:worklists":
                counts, next_publish = await self._queue_snapshot()
                await self._safe_edit_message_text(
                    query,
                    self._worklists_text(counts, next_publish),
                    reply_markup=self._worklists_keyboard(counts),
                )
                return

            if data == "sec:sources":
                await self._safe_edit_message_text(
                    query,
                    self._sources_text(),
                    reply_markup=self._sources_keyboard(),
                )
                return

            if data == "noop":
                return

            if data.startswith("srd:"):
                _, source_key = data.split(":", maxsplit=1)
                await self._safe_edit_message_text(
                    query,
                    self._source_detail_text(source_key),
                    reply_markup=self._source_detail_keyboard(source_key),
                )
                return

            if data.startswith("srt:"):
                _, source_key = data.split(":", maxsplit=1)
                catalog = source_catalog(settings)
                spec = catalog.get(source_key)
                if spec is None:
                    await query.message.reply_text("Неизвестный источник.")
                    return
                current = self._source_enabled_map(force_refresh=True).get(source_key, True)
                payload = {
                    "scope": "news",
                    "title": f"Источник: {spec.name}",
                    "description": spec.note,
                    "enabled": not current,
                    "config": {"source_key": source_key, "kind": spec.kind},
                }
                response = self.client.update_automation_control(_source_control_key(source_key), payload)
                response.raise_for_status()
                self._controls_cache = None
                await self._safe_edit_message_text(
                    query,
                    self._source_detail_text(source_key),
                    reply_markup=self._source_detail_keyboard(source_key),
                )
                return

            if data.startswith("stc:"):
                _, slug = data.split(":", maxsplit=1)
                await self._safe_edit_message_text(
                    query,
                    self._telegram_channel_detail_text(slug),
                    reply_markup=self._telegram_channel_detail_keyboard(slug),
                )
                return

            if data.startswith("scc:"):
                _, slug = data.split(":", maxsplit=1)
                normalized = _telegram_channel_slug(slug)
                current = self._telegram_channel_enabled_map(force_refresh=True).get(normalized, True)
                payload = {
                    "scope": "news",
                    "title": f"Telegram-канал: @{normalized}",
                    "description": _telegram_channel_note(normalized),
                    "enabled": not current,
                    "config": {"channel_slug": normalized, "kind": "telegram_channel"},
                }
                response = self.client.update_automation_control(_telegram_channel_control_key(normalized), payload)
                response.raise_for_status()
                self._controls_cache = None
                await self._safe_edit_message_text(
                    query,
                    self._telegram_channel_detail_text(normalized),
                    reply_markup=self._telegram_channel_detail_keyboard(normalized),
                )
                return

            if data.startswith("src:"):
                _, domain, offset_raw = data.split(":", maxsplit=2)
                offset = int(offset_raw)
                total, rows = self._load_source_posts(domain, offset)
                await self._safe_edit_message_text(
                    query,
                    self._source_posts_text(domain, total, rows, offset),
                    reply_markup=self._source_posts_keyboard(domain, total, rows, offset),
                )
                return

            if data == "sec:themes":
                counts = self._theme_stats()
                await self._safe_edit_message_text(
                    query,
                    self._themes_text(counts),
                    reply_markup=self._themes_keyboard(counts),
                )
                return

            if data == "sec:generate":
                controls = self._controls_map(force_refresh=True)
                previews = context.user_data.get(_STATE_GENERATION_PREVIEWS) or []
                await self._safe_edit_message_text(
                    query,
                    self._generation_text(controls),
                    reply_markup=self._generation_keyboard(len(previews)),
                )
                return

            if data.startswith("th:"):
                _, pillar, offset_raw = data.split(":", maxsplit=2)
                offset = int(offset_raw)
                total, rows = self._load_theme_posts(pillar, offset)
                await self._safe_edit_message_text(
                    query,
                    self._theme_posts_text(pillar, total, rows, offset),
                    reply_markup=self._theme_posts_keyboard(pillar, total, rows, offset),
                )
                return

            if data.startswith("gen:pick:"):
                limit = int(data.split(":")[-1])
                await self._safe_edit_message_text(
                    query,
                    f"Подбираю {limit} кандидатов и собираю драфты. Это может занять до минуты...",
                    reply_markup=InlineKeyboardMarkup([[_inline_button("❌ Отменить", callback_data="sec:generate")]]),
                )
                result = await asyncio.to_thread(collect_generation_previews, limit)
                previews = result.previews
                context.user_data[_STATE_GENERATION_PREVIEWS] = previews
                await self._safe_edit_message_text(
                    query,
                    self._generation_preview_list_text(previews, 0),
                    reply_markup=self._generation_preview_list_keyboard(previews, 0) if previews else self._generation_keyboard(),
                )
                return

            if data == "gen:clear":
                context.user_data.pop(_STATE_GENERATION_PREVIEWS, None)
                controls = self._controls_map(force_refresh=True)
                await self._safe_edit_message_text(
                    query,
                    self._generation_text(controls),
                    reply_markup=self._generation_keyboard(0),
                )
                return

            if data.startswith("gen:list:"):
                offset = int(data.split(":")[-1])
                previews = context.user_data.get(_STATE_GENERATION_PREVIEWS) or []
                await self._safe_edit_message_text(
                    query,
                    self._generation_preview_list_text(previews, offset),
                    reply_markup=self._generation_preview_list_keyboard(previews, offset) if previews else self._generation_keyboard(),
                )
                return

            if data.startswith("gen:view:"):
                index = int(data.split(":")[-1])
                previews = context.user_data.get(_STATE_GENERATION_PREVIEWS) or []
                if not previews or index < 0 or index >= len(previews):
                    controls = self._controls_map(force_refresh=True)
                    await self._safe_edit_message_text(
                        query,
                        "Список драфтов устарел. Подберите кандидатов заново.",
                        reply_markup=self._generation_keyboard(0),
                    )
                    return
                preview = previews[index]
                await self._safe_edit_message_text(
                    query,
                    self._generation_preview_card_text(preview, index, len(previews)),
                    reply_markup=self._generation_preview_card_keyboard(preview, index, len(previews)),
                )
                return

            if data.startswith("gen:save:"):
                index = int(data.split(":")[-1])
                previews = context.user_data.get(_STATE_GENERATION_PREVIEWS) or []
                if not previews or index < 0 or index >= len(previews):
                    controls = self._controls_map(force_refresh=True)
                    await self._safe_edit_message_text(
                        query,
                        "Список драфтов устарел. Подберите кандидатов заново.",
                        reply_markup=self._generation_keyboard(0),
                    )
                    return
                preview = previews.pop(index)
                payload = {
                    "title": preview["title"],
                    "text": preview["text"],
                    "rubric": preview["rubric"],
                    "format_type": preview["format_type"],
                    "cta_type": preview["cta_type"],
                    "source_url": preview["source_url"],
                    "source_hash": preview["source_hash"],
                    "channel_id": preview["channel_id"] or None,
                    "channel_username": preview["channel_username"] or None,
                    "publish_at": preview["publish_at"],
                    "status": "review",
                }
                response = self.client.create_scheduled_post(payload)
                if response.status_code not in (200, 201, 409):
                    response.raise_for_status()
                self._invalidate_post_caches()
                context.user_data[_STATE_GENERATION_PREVIEWS] = previews
                if previews:
                    next_index = min(index, len(previews) - 1)
                    next_preview = previews[next_index]
                    await self._safe_edit_message_text(
                        query,
                        "Драфт сохранен в review.\n\n" + self._generation_preview_card_text(next_preview, next_index, len(previews)),
                        reply_markup=self._generation_preview_card_keyboard(next_preview, next_index, len(previews)),
                    )
                    return
                controls = self._controls_map(force_refresh=True)
                await self._safe_edit_message_text(
                    query,
                    "Драфт сохранен в review. Список кандидатов очищен.",
                    reply_markup=self._generation_keyboard(0),
                )
                return

            if data == "automation":
                controls = self._load_controls(force_refresh=True)
                await self._safe_edit_message_text(
                    query,
                    self._controls_text(controls),
                    reply_markup=self._automation_keyboard(controls),
                )
                return

            if data == "status":
                controls = self._load_controls()
                await self._safe_edit_message_text(
                    query,
                    await self._panel_text(controls) + "\n\n" + await self._queue_text(),
                )
                return

            if data == "workers":
                response = self.admin_client.workers_status()
                response.raise_for_status()
                await self._safe_edit_message_text(
                    query,
                    _format_workers_status(response.json()),
                )
                return

            if data == "resetstale":
                reset_posts = self.admin_client.reset_stale_scheduled_posts(older_than_minutes=30)
                reset_posts.raise_for_status()
                reset_contract = self.admin_client.reset_stale_contract_jobs(older_than_minutes=30)
                reset_contract.raise_for_status()
                body_posts = reset_posts.json()
                body_contract = reset_contract.json()
                self._invalidate_post_caches()
                controls = self._load_controls(force_refresh=True)
                await self._safe_edit_message_text(
                    query,
                    "Сброс зависших задач выполнен.\n"
                    f"scheduled_posts: {body_posts.get('reset_count', 0)}\n"
                    f"contract_jobs: {body_contract.get('reset_count', 0)}",
                    reply_markup=self._automation_keyboard(controls),
                )
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

            controls = self._load_controls(force_refresh=True)
            await self._safe_edit_message_text(
                query,
                self._controls_text(controls),
                reply_markup=self._automation_keyboard(controls),
            )
        except Exception as exc:
            logger.exception("admin_callback_failed", extra={"callback_data": data, "error": str(exc)})
            if _is_scope_error(exc):
                await query.message.reply_text(
                    "Операция требует ключ со scope `admin`.\n"
                    "Укажите `API_KEY_ADMIN` в .env и перезапустите admin-бот."
                )
            else:
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
                await self._safe_edit_message_text(query, 
                    self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                    reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                )
                return

            if data.startswith("mbp:"):
                queue_filter, offset, mode = _parse_batch_publish_callback(data)
                if not _is_batch_mode_allowed(queue_filter, mode):
                    total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
                    await self._safe_edit_message_text(query, 
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
                    await self._safe_edit_message_text(query, 
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
                await self._safe_edit_message_text(query, 
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
                    await self._safe_edit_message_text(query, 
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
                await self._safe_edit_message_text(query, 
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
                await self._safe_edit_message_text(query, 
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
                await self._safe_edit_message_text(query, 
                    self._posts_text(total, rows, offset, status),
                    reply_markup=self._posts_keyboard(total, rows, offset, status),
                )
                return

            if data.startswith("pv:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                post = self._get_post(post_id)
                await self._safe_edit_message_text(query, 
                    self._post_card_text(post),
                    reply_markup=self._post_card_keyboard(post_id, status, offset),
                )
                return

            if data.startswith("pdd:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                context.user_data[_STATE_PENDING_DELETE_REASON] = {
                    "post_id": post_id,
                    "status": status,
                    "offset": offset,
                }
                await self._safe_edit_message_text(
                    query,
                    "Удаление нерелевантного поста\n\n"
                    "Коротко напишите причину. Этот сигнал будет записан в feedback и использован для дальнейшей фильтрации генерации.\n\n"
                    "Примеры:\n"
                    "• общая AI-новость без связи с юрфункцией\n"
                    "• новость про рынок IT, не про legal AI\n"
                    "• нет юридического сценария применения\n"
                    "• слишком общий материал, без пользы для канала",
                    reply_markup=self._delete_reason_keyboard(post_id, status, offset),
                )
                return

            if data.startswith("pdn:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                context.user_data.pop(_STATE_PENDING_DELETE_REASON, None)
                post = self._get_post(post_id)
                await self._safe_edit_message_text(
                    query,
                    self._post_card_text(post),
                    reply_markup=self._post_card_keyboard(post_id, status, offset),
                )
                return

            if data.startswith("pdy:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                pending = context.user_data.get(_STATE_PENDING_DELETE_REASON) or {}
                reason = str(pending.get("reason") or "").strip()
                if not reason:
                    await self._safe_edit_message_text(
                        query,
                        "Сначала укажите причину удаления.",
                        reply_markup=self._delete_reason_keyboard(post_id, status, offset),
                    )
                    return
                feedback_response = self.client.create_post_feedback(
                    post_id,
                    {
                        "source": "comment",
                        "signal_key": "irrelevant_delete",
                        "signal_value": -2,
                        "text": reason,
                        "actor_name": "admin_delete",
                        "payload": {
                            "kind": "admin_delete",
                            "reason": reason,
                            "status_before_delete": status,
                        },
                    },
                )
                feedback_response.raise_for_status()
                delete_response = self.client.delete_post(post_id)
                if delete_response.status_code not in (200, 202, 204):
                    delete_response.raise_for_status()
                context.user_data.pop(_STATE_PENDING_DELETE_REASON, None)
                self._invalidate_post_caches()

                if _is_theme_context(status):
                    pillar = _theme_from_context(status)
                    total, rows = self._load_theme_posts(pillar, offset)
                    await self._safe_edit_message_text(
                        query,
                        "Пост удален, негативный feedback сохранен.\n\n" + self._theme_posts_text(pillar, total, rows, offset),
                        reply_markup=self._theme_posts_keyboard(pillar, total, rows, offset),
                    )
                    return
                if _is_source_context(status):
                    domain = _source_from_context(status)
                    total, rows = self._load_source_posts(domain, offset)
                    await self._safe_edit_message_text(
                        query,
                        "Пост удален, негативный feedback сохранен.\n\n" + self._source_posts_text(domain, total, rows, offset),
                        reply_markup=self._source_posts_keyboard(domain, total, rows, offset),
                    )
                    return
                if _is_manual_queue_context(status):
                    queue_filter = _queue_filter_from_context(status)
                    total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset)
                    await self._safe_edit_message_text(
                        query,
                        "Пост удален, негативный feedback сохранен.\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                    )
                    return
                if _is_calendar_context(status):
                    day_key = _calendar_date_from_context(status)
                    rows = self._calendar_day_rows(day_key)
                    await self._safe_edit_message_text(
                        query,
                        "Пост удален, негативный feedback сохранен.\n\n" + self._calendar_day_text(day_key, rows),
                        reply_markup=self._calendar_day_keyboard(day_key, rows),
                    )
                    return

                total, rows = self._load_posts(status=status, offset=offset)
                await self._safe_edit_message_text(
                    query,
                    "Пост удален, негативный feedback сохранен.\n\n" + self._posts_text(total, rows, offset, status),
                    reply_markup=self._posts_keyboard(total, rows, offset, status),
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
                self._invalidate_post_caches()
                post = self._get_post(post_id)
                await self._safe_edit_message_text(query, 
                    f"Пост перепланирован: {_slot_label(slot)}.\n\n" + self._post_card_text(post),
                    reply_markup=self._post_card_keyboard(post_id, status, offset),
                )
                return

            if data.startswith("pr:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                post = self._get_post(post_id)
                self.client.patch_post(post_id, self._ready_status_payload(post)).raise_for_status()
                self._invalidate_post_caches()
                if _is_theme_context(status):
                    pillar = _theme_from_context(status)
                    total, rows = self._load_theme_posts(pillar, offset)
                    await self._safe_edit_message_text(
                        query,
                        "Пост переведён в готовые (scheduled).\n\n" + self._theme_posts_text(pillar, total, rows, offset),
                        reply_markup=self._theme_posts_keyboard(pillar, total, rows, offset),
                    )
                    return
                total, rows = self._load_posts(status="scheduled", offset=0)
                await self._safe_edit_message_text(query, 
                    "Пост переведён в готовые (scheduled).\n\n" + self._posts_text(total, rows, 0, "scheduled"),
                    reply_markup=self._posts_keyboard(total, rows, 0, "scheduled"),
                )
                return

            if data.startswith("rr:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                self.client.patch_post(post_id, {"status": "review"}).raise_for_status()
                self._invalidate_post_caches()
                if _is_theme_context(status):
                    pillar = _theme_from_context(status)
                    total, rows = self._load_theme_posts(pillar, offset)
                    await self._safe_edit_message_text(
                        query,
                        "Пост переведён в проверку (review).\n\n" + self._theme_posts_text(pillar, total, rows, offset),
                        reply_markup=self._theme_posts_keyboard(pillar, total, rows, offset),
                    )
                    return
                total, rows = self._load_posts(status="review", offset=0)
                await self._safe_edit_message_text(
                    query,
                    "Пост переведён в проверку (review).\n\n" + self._posts_text(total, rows, 0, "review"),
                    reply_markup=self._posts_keyboard(total, rows, 0, "review"),
                )
                return

            if data.startswith("ba:"):
                _, action, status, offset_raw = data.split(":", maxsplit=3)
                if action not in {"ready", "review"}:
                    await query.message.reply_text("Неизвестное пакетное действие.")
                    return
                offset = int(offset_raw)
                total, rows = self._load_posts(status=status, offset=offset)
                moved = 0
                for row in rows:
                    post_id = str(row.get("id"))
                    try:
                        target_status = "scheduled" if action == "ready" else "review"
                        payload = {"status": target_status}
                        if action == "ready":
                            payload = self._ready_status_payload(row)
                        self.client.patch_post(post_id, payload).raise_for_status()
                        moved += 1
                    except Exception:
                        logger.exception("batch_move_failed", extra={"post_id": post_id, "from_status": status})
                if moved:
                    self._invalidate_post_caches()
                total_after, rows_after = self._load_posts(status=status, offset=offset)
                await self._safe_edit_message_text(query, 
                    f"Готово: {moved} пост(ов) переведены в {'scheduled' if action == 'ready' else 'review'}.\n\n"
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
                await self._safe_edit_message_text(query, 
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
                await self._safe_edit_message_text(query, 
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
                    await self._safe_edit_message_text(query, 
                        f"Пост успешно опубликован вручную.\nПричина: {reason}\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                    )
                elif _is_source_context(status):
                    domain = _source_from_context(status)
                    total, rows = self._load_source_posts(domain, offset)
                    await self._safe_edit_message_text(
                        query,
                        f"Пост успешно опубликован вручную.\nПричина: {reason}\n\n"
                        + self._source_posts_text(domain, total, rows, offset),
                        reply_markup=self._source_posts_keyboard(domain, total, rows, offset),
                    )
                elif _is_theme_context(status):
                    pillar = _theme_from_context(status)
                    total, rows = self._load_theme_posts(pillar, offset)
                    await self._safe_edit_message_text(
                        query,
                        f"Пост успешно опубликован вручную.\nПричина: {reason}\n\n"
                        + self._theme_posts_text(pillar, total, rows, offset),
                        reply_markup=self._theme_posts_keyboard(pillar, total, rows, offset),
                    )
                elif _is_calendar_context(status):
                    day_key = _calendar_date_from_context(status)
                    rows = self._calendar_day_rows(day_key)
                    await self._safe_edit_message_text(
                        query,
                        f"Пост успешно опубликован вручную.\nПричина: {reason}\n\n"
                        + self._calendar_day_text(day_key, rows),
                        reply_markup=self._calendar_day_keyboard(day_key, rows),
                    )
                else:
                    total, rows = self._load_posts(status=status, offset=offset)
                    await self._safe_edit_message_text(query, 
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
                self._invalidate_post_caches()
                context.user_data.pop(_STATE_DRAFT_EDIT, None)
                context.user_data.pop(_STATE_PENDING_EDIT, None)

                post = self._get_post(post_id)
                await self._safe_edit_message_text(query, 
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
                    await self._safe_edit_message_text(query, 
                        "Редактирование отменено.\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter),
                    )
                elif _is_source_context(status):
                    domain = _source_from_context(status)
                    total, rows = self._load_source_posts(domain, offset)
                    await self._safe_edit_message_text(
                        query,
                        "Редактирование отменено.\n\n" + self._source_posts_text(domain, total, rows, offset),
                        reply_markup=self._source_posts_keyboard(domain, total, rows, offset),
                    )
                elif _is_theme_context(status):
                    pillar = _theme_from_context(status)
                    total, rows = self._load_theme_posts(pillar, offset)
                    await self._safe_edit_message_text(
                        query,
                        "Редактирование отменено.\n\n" + self._theme_posts_text(pillar, total, rows, offset),
                        reply_markup=self._theme_posts_keyboard(pillar, total, rows, offset),
                    )
                elif _is_calendar_context(status):
                    day_key = _calendar_date_from_context(status)
                    rows = self._calendar_day_rows(day_key)
                    await self._safe_edit_message_text(
                        query,
                        "Редактирование отменено.\n\n" + self._calendar_day_text(day_key, rows),
                        reply_markup=self._calendar_day_keyboard(day_key, rows),
                    )
                else:
                    total, rows = self._load_posts(status=status, offset=offset)
                    await self._safe_edit_message_text(query, 
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
        pending_day_publish_reason = context.user_data.get(_STATE_PENDING_DAY_PUBLISH_REASON)
        if pending_day_publish_reason:
            reason = _normalize_operator_note(message_text)
            if not reason:
                await update.effective_message.reply_text("Причина не должна быть пустой. Пришлите сообщение ещё раз.")
                return
            day_key = str(pending_day_publish_reason.get("day_key") or "")
            post_ids = [str(item) for item in pending_day_publish_reason.get("post_ids", []) if item]
            if not day_key or not post_ids:
                context.user_data.pop(_STATE_PENDING_DAY_PUBLISH_REASON, None)
                await update.effective_message.reply_text("Список постов для дня пуст. Запустите действие заново.")
                return
            context.user_data[_STATE_DRAFT_DAY_PUBLISH] = {
                "day_key": day_key,
                "post_ids": post_ids,
                "reason": reason,
            }
            context.user_data.pop(_STATE_PENDING_DAY_PUBLISH_REASON, None)
            await update.effective_message.reply_text(
                "Пакетная публикация дня: шаг 2 из 2\n\n"
                f"Дата: {day_key}\n"
                f"Постов: {len(post_ids)}\n"
                f"Причина: {reason}\n\n"
                "Подтвердите публикацию этого дня:",
                reply_markup=self._day_publish_confirm_keyboard(day_key),
            )
            return

        pending_delete_reason = context.user_data.get(_STATE_PENDING_DELETE_REASON)
        if pending_delete_reason:
            reason = _normalize_operator_note(message_text)
            if not reason:
                await update.effective_message.reply_text("Причина не должна быть пустой. Пришлите сообщение ещё раз.")
                return
            post_id = str(pending_delete_reason.get("post_id") or "")
            status = str(pending_delete_reason.get("status") or "review")
            offset = int(pending_delete_reason.get("offset") or 0)
            pending_delete_reason["reason"] = reason
            context.user_data[_STATE_PENDING_DELETE_REASON] = pending_delete_reason
            await update.effective_message.reply_text(
                "Удаление нерелевантного поста\n\n"
                f"ID: {post_id}\n"
                f"Причина: {reason}\n\n"
                "Подтвердите удаление. Сначала будет записан негативный feedback, потом пост удалится.",
                reply_markup=self._delete_confirm_keyboard(post_id, status, offset),
            )
            return

        pending_create = context.user_data.get(_STATE_PENDING_CREATE)
        if pending_create:
            if not message_text:
                await update.effective_message.reply_text("Пустой текст не подходит. Пришлите сообщение ещё раз.")
                return

            mode = str(pending_create.get("mode") or "manual")
            step = str(pending_create.get("step") or "title")
            title = str(pending_create.get("title") or "").strip()

            try:
                if step == "title":
                    title = message_text
                    if mode == "manual":
                        context.user_data[_STATE_PENDING_CREATE] = {"mode": mode, "step": "text", "title": title}
                        await update.effective_message.reply_text(
                            "Новый пост: шаг 2 из 2\n\n"
                            f"Заголовок: {title}\n\n"
                            "Пришлите полный текст поста одним сообщением.",
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton("❌ Отменить", callback_data="cn:cancel")]]
                            ),
                        )
                        return

                    context.user_data[_STATE_PENDING_CREATE] = {"mode": mode, "step": "brief", "title": title}
                    await update.effective_message.reply_text(
                        "Новый пост через LLM: шаг 2 из 2\n\n"
                        f"Заголовок: {title}\n\n"
                        "Пришлите тезисы, вводные или структуру будущего поста.",
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("❌ Отменить", callback_data="cn:cancel")]]
                        ),
                    )
                    return

                if step == "text":
                    draft = {"mode": mode, "title": title, "text": message_text}
                    context.user_data[_STATE_DRAFT_CREATE] = draft
                    context.user_data.pop(_STATE_PENDING_CREATE, None)
                    await self._show_create_draft(update.effective_message, draft)
                    return

                if step == "brief":
                    draft_text = self._draft_post_with_llm(title, message_text)
                    draft = {"mode": mode, "title": title, "text": draft_text, "brief": message_text}
                    context.user_data[_STATE_DRAFT_CREATE] = draft
                    context.user_data.pop(_STATE_PENDING_CREATE, None)
                    await self._show_create_draft(update.effective_message, draft)
                    return

                if step in _CREATE_EDIT_STEPS:
                    draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
                    if not draft:
                        context.user_data.pop(_STATE_PENDING_CREATE, None)
                        await update.effective_message.reply_text("Активный черновик не найден. Запустите создание заново.")
                        return

                    if step == "edit_title":
                        draft["title"] = message_text
                    elif step == "edit_text":
                        draft["text"] = message_text
                    elif step == "edit_ai":
                        draft["text"] = self._rewrite_with_llm(str(draft.get("text") or ""), message_text)
                    context.user_data[_STATE_DRAFT_CREATE] = draft
                    context.user_data.pop(_STATE_PENDING_CREATE, None)
                    await self._show_create_draft(update.effective_message, draft)
                    return
            except Exception as exc:
                logger.exception("create_text_failed", extra={"mode": mode, "step": step, "error": str(exc)})
                await update.effective_message.reply_text(f"Ошибка создания поста: {exc}")
                return

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
            if _button_text_equals(message_text, _MAIN_MENU_PANEL):
                await self.cmd_panel(update, context)
                return
            if _button_text_equals(message_text, _MAIN_MENU_CREATE):
                await self.cmd_new_post(update, context)
                return
            if _button_text_equals(message_text, _MAIN_MENU_CALENDAR):
                await self.cmd_calendar(update, context)
                return
            if _button_text_equals(message_text, _MAIN_MENU_SECTIONS):
                await self.cmd_sections(update, context)
                return
            if _button_text_equals(message_text, _MAIN_MENU_HELP):
                await self.cmd_help(update, context)
                return
            await update.effective_message.reply_text(
                "Используйте кнопки меню ниже. Для возврата к панели нажмите «🏠 Панель».",
                reply_markup=_main_menu_markup(),
            )
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

        app = Application.builder().token(bot_token).post_init(self._post_init).build()
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("admin", self.cmd_panel))
        app.add_handler(CommandHandler("sections", self.cmd_sections))
        app.add_handler(CommandHandler("sources", self.cmd_sources))
        app.add_handler(CommandHandler("themes", self.cmd_themes))
        app.add_handler(CommandHandler("newpost", self.cmd_new_post))
        app.add_handler(CommandHandler("generate_now", self.cmd_generate_now))
        app.add_handler(CommandHandler("calendar", self.cmd_calendar))
        app.add_handler(CommandHandler("controls", self.cmd_panel))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("posts", self.cmd_posts))
        app.add_handler(CommandHandler("queue", self.cmd_queue))
        app.add_handler(CommandHandler("workers", self.cmd_workers))
        app.add_handler(CommandHandler("cancel_edit", self.cmd_cancel_edit))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(
            CallbackQueryHandler(
                self.cb_calendar,
                pattern=r"^(cal:summary|cal:day:\d{4}-\d{2}-\d{2}|cav:[0-9a-f-]{36}:\d{4}-\d{2}-\d{2}|cap:\d{4}-\d{2}-\d{2}|cpc:\d{4}-\d{2}-\d{2}|cpn:\d{4}-\d{2}-\d{2}|cas:(?:tomorrow|spread):\d{4}-\d{2}-\d{2}|car:\d{4}-\d{2}-\d{2}:\d{4})$",
            )
        )
        app.add_handler(
            CallbackQueryHandler(
                self.cb_create,
                pattern=r"^(cn:(?:start|manual|ai|cancel)|cd:view|ce:(?:title|text|ai)|cs:(?:draft|review)|cs:scheduled:(?:h1|e19|t10))$",
            )
        )
        app.add_handler(
            CallbackQueryHandler(
                self.cb_controls,
                pattern=r"^(noop|refresh|sections|automation|status|workers|resetstale|sec:(?:worklists|sources|themes|generate)|srd:[a-z0-9_.-]+|srt:[a-z0-9_.-]+|stc:[a-z0-9_.-]+|scc:[a-z0-9_.-]+|src:[a-z0-9_.-]+:\d+|th:[a-z]+:\d+|gen:(?:pick:\d+|list:\d+|view:\d+|save:\d+|clear)|all:[01]|set:[a-z0-9_.-]+:[01])$",
            )
        )
        app.add_handler(
            CallbackQueryHandler(
                self.cb_posts,
                pattern=r"^(mq:(?:due|all):\d+|mq:\d+|mbp:(?:due|all):\d+(?::(?:page|top3|top5))?|mbc:(?:due|all):\d+(?::(?:page|top3|top5))?|mbn:(?:due|all):\d+(?::(?:page|top3|top5))?|pl:(?:draft|review|scheduled|posted|failed):\d+|pl:\d+|pv:[0-9a-f-]{36}:(?:draft|review|scheduled|posted|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|pt:[0-9a-f-]{36}:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+:(?:h1|e19|t10)|ppc:[0-9a-f-]{36}:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|ppy:[0-9a-f-]{36}:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|ppn:[0-9a-f-]{36}:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|pdd:[0-9a-f-]{36}:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|pdn:[0-9a-f-]{36}:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|pdy:[0-9a-f-]{36}:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|pm:[0-9a-f-]{36}:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|pa:[0-9a-f-]{36}:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|rr:[0-9a-f-]{36}:draft:\d+|pr:[0-9a-f-]{36}:(?:review|failed):\d+|ps:[0-9a-f-]{36}:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|px:(?:draft|review|scheduled|failed|mq_due|mq_all|cal_\d{8}|th_[a-z]+|src_[a-z0-9_.-]+):\d+|ba:(?:ready:(?:review|failed)|review:draft):\d+)$",
            )
        )
        app.add_handler(
            MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, self.on_edit_text)
        )
        app.add_handler(MessageReactionHandler(self.on_feedback_reaction_count, message_reaction_types=MessageReactionHandler.MESSAGE_REACTION_COUNT_UPDATED))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_feedback_message))

        logger.info("news_admin_bot_started", extra={"admins": sorted(self.admin_ids)})
        app.run_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)
        return 0


def main() -> int:
    return NewsAdminBot().run()


if __name__ == "__main__":
    raise SystemExit(main())
