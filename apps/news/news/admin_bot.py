from __future__ import annotations

import asyncio
import html
import hashlib
import logging
import os
import re
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote
from zoneinfo import ZoneInfo

from telegram import (
    BotCommand,
    InputMediaPhoto,
    InputMediaVideo,
    InlineKeyboardButton as _PTBInlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton as _PTBKeyboardButton,
    Message,
    MessageReactionCountUpdated,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
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
from news.llm_writer import build_manual_footer, compose_manual_post_html
from news.logging_config import setup_logging
from news.pipeline import (
    GENERATION_THEME_DEFS,
    extract_domain,
    generation_theme_keys,
    generation_theme_label,
    generation_theme_note,
    generation_themes_for_text,
    normalize_post_text,
    normalize_rubric_to_pillar,
)
from news.settings import settings
from news.source_catalog import active_source_specs, resolve_source_urls, source_catalog
from news.strategy import (
    build_schedule_window,
    publication_kind_badge,
    publication_kind_from_format_type,
    publication_kind_label,
    resolve_schedule_config,
    schedule_alias_meta,
    schedule_aliases,
    schedule_control_key,
    schedule_slot_label,
)

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
_CREATE_EDIT_STEPS = {"edit_title", "edit_text", "edit_source", "edit_link", "edit_ai"}
_POST_LIST_STATUSES = ("draft", "review", "scheduled", "posted", "failed")
_MANUAL_QUEUE_FILTERS = ("due", "all")
_AUTO_QUEUE_FILTERS = ("all", "daily", "weekly_review", "longread", "humor", "other")
_REVIEW_SOURCE_FILTERS = ("all", "ai", "manual")
_BATCH_PUBLISH_MODES = ("page", "top3", "top5")
_INTERVAL_SETTING_KINDS = (
    "generate_morning",
    "generate_evening",
    "publish",
    "limit",
    "retention",
    "broad_ai",
    "telegram_morning",
    "telegram_evening",
    "telegram_limit",
)
_MAIN_MENU_WORKSPACE = "🏠 Рабочий стол"
_MAIN_MENU_CREATE = "➕ Создать"

_BUTTON_STYLE_PRIMARY = None
_BUTTON_STYLE_SUCCESS = "success"
_BUTTON_STYLE_DANGER = "danger"
_NEWS_ADMIN_BUTTON_ICON_ENV = "NEWS_ADMIN_BUTTON_ICON_MAP"
_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_POST_CACHE_TTL_SECONDS = 12
_QUEUE_CACHE_TTL_SECONDS = 15
_DERIVED_CACHE_TTL_SECONDS = 20
_CALENDAR_CACHE_TTL_SECONDS = 20

_PILLAR_LABELS = {
    "regulation": "AI в праве и регулирование",
    "case": "Кейсы внедрения в юрфункции",
    "implementation": "Автоматизация юрфункции и legal ops",
    "tools": "AI-инструменты для практики юриста",
    "market": "Рынок Legal AI и legal tech",
}
_PILLAR_BADGES = {
    "regulation": "⚖️",
    "case": "📚",
    "implementation": "⚙️",
    "tools": "🧰",
    "market": "📈",
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
_QUEUE_THEME_FILTERS = ("all",) + tuple(_PILLAR_LABELS)
_LONGREAD_TOPIC_LIBRARY = tuple(dict.fromkeys(settings.news_longread_topics_list))
_CALENDAR_CALLBACK_PREFIXES = ("cal:", "cav:", "cap:", "cpc:", "cpn:", "cas:", "car:")
_CREATE_CALLBACK_PREFIXES = ("cn:", "ck:", "ct:", "cm:", "cl:", "cd:", "cr:", "ce:", "cs:")
_CONTROLS_CALLBACK_EXACT = frozenset({"noop", "refresh", "sections", "automation", "status", "workers", "resetstale"})
_CONTROLS_CALLBACK_PREFIXES = (
    "sch:",
    "int:",
    "sec:",
    "thm:",
    "aq:",
    "srd:",
    "srt:",
    "stc:",
    "scc:",
    "src:",
    "th:",
    "lt:",
    "gt:",
    "fa:",
    "gen:",
    "preset:",
    "all:",
    "set:",
    "wrk:",
)
_POSTS_CALLBACK_PREFIXES = (
    "mq:",
    "mbp:",
    "mbc:",
    "mbn:",
    "pl:",
    "rv:",
    "pv:",
    "pt:",
    "ppc:",
    "ppy:",
    "ppn:",
    "pdd:",
    "pdn:",
    "pdy:",
    "pm:",
    "pa:",
    "pf:",
    "rr:",
    "pr:",
    "ps:",
    "px:",
    "ba:",
)
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
_WORKER_LABELS = {
    "news-generate": "🧠 Генератор драфтов",
    "news-telegram-ingest": "📡 Telegram-парсер",
    "news-publish": "📤 Публикатор канала",
}
_MANUAL_POST_TYPES = {
    "promo_offer": {
        "label": "Рекламный",
        "note": "Прямой оффер по услуге, продукту или формату внедрения.",
        "llm_hint": "Собери продающий, но деловой пост: боль -> решение -> результат -> мягкий CTA.",
        "style_hint": "Тон уверенный и предметный. Никакого агрессивного продавливания. Покажи узкое место клиента, объясни формат решения и зафиксируй реалистичный следующий шаг.",
        "rubric": "legal_ops",
    },
    "product_review": {
        "label": "Обзор продукта",
        "note": "Разбор модуля, сервиса, AI-решения или продукта для юрфункции.",
        "llm_hint": "Сделай обзор продукта: контекст, задачи, кому подходит, ограничения, следующий шаг.",
        "style_hint": "Тон редакционный и аналитический. Не продавай продукт автоматически. Покажи, где он полезен, где слаб, и для какой команды он реально подходит.",
        "rubric": "legal_ops",
    },
    "case_story": {
        "label": "Кейс внедрения",
        "note": "Практический кейс: что было, что сделали, какой эффект.",
        "llm_hint": "Собери кейсовый пост: исходная проблема, архитектура решения, эффект, вывод.",
        "style_hint": "Тон конкретный и практический. Обязательно покажи исходную проблему, изменение процесса и результат без хвастовства и фантазий.",
        "rubric": "legal_ops",
    },
    "opinion": {
        "label": "Мнение",
        "note": "Авторская позиция по тренду, риску или инструменту.",
        "llm_hint": "Сделай сильный opinion post: тезис, аргументы, последствия для юрфункции, вывод.",
        "style_hint": "Тон авторский и собранный. Нужен сильный тезис, 2-3 аргумента и взрослый вывод, без истерики, лозунгов и банальностей.",
        "rubric": "ai_law",
    },
    "problem_breakdown": {
        "label": "Разбор проблемы",
        "note": "Один узкий болевой сценарий и практический разбор вариантов решения.",
        "llm_hint": "Сделай структурный разбор проблемы: где теряются деньги/время, почему, что делать.",
        "rubric": "legal_ops",
    },
    "checklist": {
        "label": "Чек-лист",
        "note": "Пошаговый список действий или критериев.",
        "llm_hint": "Собери прикладной checklist для руководителя юрфункции или юриста-практика.",
        "style_hint": "Тон утилитарный. Каждый пункт должен быть действием или критерием, а не общей фразой. Никаких длинных подводок.",
        "rubric": "legal_ops",
    },
    "faq": {
        "label": "FAQ / ответы",
        "note": "Короткий пост в формате вопросов и ответов.",
        "llm_hint": "Сделай FAQ-пост с 4-6 короткими вопросами и ответами по теме.",
        "style_hint": "Тон ясный и спокойный. Вопросы должны быть реальными, как их задает клиент или руководитель юрфункции, а ответы короткими и содержательными.",
        "rubric": "legal_ops",
    },
    "announcement": {
        "label": "Анонс",
        "note": "Анонс продукта, услуги, материала, эфира или события.",
        "llm_hint": "Сделай короткий анонс: что происходит, для кого, зачем идти, что получит аудитория.",
        "rubric": "market",
    },
    "digest": {
        "label": "Дайджест",
        "note": "Подборка нескольких тезисов, новостей или решений в одном посте.",
        "llm_hint": "Собери компактный digest по 4-6 пунктам, каждый с практической пользой.",
        "rubric": "market",
    },
    "service_page": {
        "label": "Услуга / решение",
        "note": "Объяснение конкретной услуги: что делаем, где применимо, какой следующий шаг.",
        "llm_hint": "Собери пост-страницу услуги: задача клиента, что делаем, результат, когда это нужно.",
        "rubric": "legal_ops",
    },
}
_MANUAL_POST_TYPE_ORDER = tuple(_MANUAL_POST_TYPES)
_MANUAL_THEMES = {
    "legal_function_ai": {
        "label": "AI в работе юротдела",
        "note": "Процессы, загрузка команды, SLA, скорость и качество работы юрфункции.",
        "rubric": "legal_ops",
    },
    "contracts_ai": {
        "label": "AI в договорной работе",
        "note": "Согласование, redlining, review, playbook, контроль рисков по договорам.",
        "rubric": "contracts",
    },
    "leads_ai": {
        "label": "AI в обработке заявок",
        "note": "Intake, triage, первичная квалификация, маршрутизация и клиентский контур.",
        "rubric": "legal_ops",
    },
    "documents_ai": {
        "label": "AI в документообороте",
        "note": "Шаблоны, сбор данных, генерация и контроль качества юридических документов.",
        "rubric": "legal_ops",
    },
    "disputes_ai": {
        "label": "AI в судебной и претензионной работе",
        "note": "Споры, eDiscovery, legal hold, аналитика позиции и прогнозирование исхода.",
        "rubric": "litigation",
    },
    "privacy_compliance_ai": {
        "label": "AI в комплаенсе и рисках",
        "note": "ПДн, privacy, AI governance, внутренний контроль, аудит и регуляторика.",
        "rubric": "privacy",
    },
    "legal_ops_automation": {
        "label": "Legal Ops и автоматизация процессов",
        "note": "Операционная модель юрфункции, экономия времени, качество и метрики.",
        "rubric": "legal_ops",
    },
    "tools_products_ai": {
        "label": "AI-продукты для юристов",
        "note": "Инструменты, платформы, продуктовые решения и vendor evaluation.",
        "rubric": "market",
    },
    "ai_regulation": {
        "label": "Регулирование AI",
        "note": "AI Act, privacy law, sanctions, экспортные ограничения и AI law.",
        "rubric": "regulation",
    },
    "legal_ai_market": {
        "label": "Рынок Legal AI и кейсы",
        "note": "Сделки, рост вендоров, кейсы внедрения и сигналы рынка Legal AI.",
        "rubric": "market",
    },
}
_MANUAL_THEME_ORDER = tuple(_MANUAL_THEMES)
_FOOTER_BLOCK_RE = re.compile(
    r"(?:\n\n)?<b>Следующий шаг</b>\n.*?(?=(?:\n\n<b>Источник</b>|\n<b>Источник</b>|\n\n#|$))",
    re.DOTALL,
)
_FOOTER_VARIANT_HINTS = (
    "Начни с мягкой формулы типа «Если у вас похожая задача...» или «Если для вашей команды это тоже актуально...»",
    "Начни с практического разворота типа «Такие сценарии уже можно внедрять в...» без рекламной напористости.",
    "Начни с делового приглашения к разбору кейса, а не с прямой продажи. Подход: «Если хотите разобрать ваш процесс...»",
    "Начни с перехода от сигнала к действию: «Из таких кейсов обычно вырастают проекты по...»",
    "Начни с осторожного вывода: «На практике такие решения полезно примерять на...»",
    "Начни с формулы про следующий шаг внедрения: «Если думаете, как внедрить подобный сценарий...»",
)


def _is_hidden_deleted_post(row: dict[str, Any]) -> bool:
    last_error = str(row.get("last_error") or "").strip().lower()
    return last_error.startswith("deleted_irrelevant") or last_error.startswith("expired_review_cleanup")


def _status_label(status: str) -> str:
    if _is_calendar_context(status):
        return "🗓 Календарь публикаций"
    if _is_auto_queue_context(status):
        queue_filter, theme_filter = _auto_queue_filters_from_context(status)
        theme_suffix = "" if theme_filter == "all" else f" / {_pillar_display(theme_filter)}"
        if queue_filter == "all":
            return f"⏱ Автоочередь{theme_suffix}"
        return f"⏱ Автоочередь: {publication_kind_label(queue_filter)}{theme_suffix}"
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


def _parse_review_filter_callback(data: str) -> tuple[str, str, str, int]:
    parts = data.split(":")
    review_filter = "all"
    kind_filter = "all"
    theme_filter = "all"
    offset = 0
    if len(parts) >= 2 and parts[1] in _REVIEW_SOURCE_FILTERS:
        review_filter = parts[1]
    if len(parts) >= 3 and parts[2] in _AUTO_QUEUE_FILTERS:
        kind_filter = parts[2]
    if len(parts) >= 4 and parts[3] in _QUEUE_THEME_FILTERS:
        theme_filter = parts[3]
    if len(parts) >= 5:
        offset = int(parts[4])
    elif len(parts) >= 3 and parts[2].isdigit():
        offset = int(parts[2])
    return review_filter, kind_filter, theme_filter, offset


def _callback_payload_text(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    return ""


def _callback_prefix_matcher(
    payload: object,
    *,
    prefixes: tuple[str, ...] = (),
    exact: frozenset[str] | None = None,
) -> bool:
    data = _callback_payload_text(payload)
    if not data:
        return False
    if exact and data in exact:
        return True
    return any(data.startswith(prefix) for prefix in prefixes)


def _is_calendar_callback(payload: object) -> bool:
    return _callback_prefix_matcher(payload, prefixes=_CALENDAR_CALLBACK_PREFIXES)


def _is_create_callback(payload: object) -> bool:
    return _callback_prefix_matcher(payload, prefixes=_CREATE_CALLBACK_PREFIXES)


def _is_controls_callback(payload: object) -> bool:
    return _callback_prefix_matcher(
        payload,
        prefixes=_CONTROLS_CALLBACK_PREFIXES,
        exact=_CONTROLS_CALLBACK_EXACT,
    )


def _is_posts_callback(payload: object) -> bool:
    return _callback_prefix_matcher(payload, prefixes=_POSTS_CALLBACK_PREFIXES)


def _parse_manual_queue_callback(data: str) -> tuple[str, str, int]:
    # Формат: mq:<filter>:<theme>:<offset>, fallback: mq:<filter>:<offset>, legacy: mq:<offset>
    parts = data.split(":")
    if len(parts) == 2:
        return "due", "all", int(parts[1])
    if len(parts) >= 4:
        queue_filter = parts[1]
        if queue_filter not in _MANUAL_QUEUE_FILTERS:
            queue_filter = "due"
        theme_filter = parts[2]
        if theme_filter not in _QUEUE_THEME_FILTERS:
            theme_filter = "all"
        return queue_filter, theme_filter, int(parts[3])
    if len(parts) >= 3:
        queue_filter = parts[1]
        if queue_filter not in _MANUAL_QUEUE_FILTERS:
            queue_filter = "due"
        return queue_filter, "all", int(parts[2])
    return "due", "all", 0


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


def _pillar_badge(pillar: str) -> str:
    return _PILLAR_BADGES.get(pillar, "🧭")


def _pillar_display(pillar: str) -> str:
    return f"{_pillar_badge(pillar)} {_pillar_label(pillar)}"


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


def _queue_context_from_filter(queue_filter: str, theme_filter: str = "all") -> str:
    normalized_queue = "all" if queue_filter == "all" else "due"
    normalized_theme = theme_filter if theme_filter in _QUEUE_THEME_FILTERS else "all"
    return f"mq_{normalized_queue}_{normalized_theme}"


def _queue_filters_from_context(context: str) -> tuple[str, str]:
    normalized = context.removeprefix("mq_")
    parts = normalized.split("_", 1)
    queue_filter = parts[0] if parts and parts[0] in _MANUAL_QUEUE_FILTERS else "due"
    theme_filter = parts[1] if len(parts) == 2 and parts[1] in _QUEUE_THEME_FILTERS else "all"
    return queue_filter, theme_filter


def _queue_filter_from_context(context: str) -> str:
    return _queue_filters_from_context(context)[0]


def _is_manual_queue_context(context: str) -> bool:
    return context.startswith("mq_")


def _auto_queue_context(queue_filter: str, theme_filter: str = "all") -> str:
    normalized = queue_filter if queue_filter in _AUTO_QUEUE_FILTERS else "all"
    normalized_theme = theme_filter if theme_filter in _QUEUE_THEME_FILTERS else "all"
    return f"aq_{normalized}_{normalized_theme}"


def _auto_queue_filters_from_context(context: str) -> tuple[str, str]:
    normalized = context.removeprefix("aq_")
    parts = normalized.split("_", 1)
    queue_filter = parts[0] if parts and parts[0] in _AUTO_QUEUE_FILTERS else "all"
    theme_filter = parts[1] if len(parts) == 2 and parts[1] in _QUEUE_THEME_FILTERS else "all"
    return queue_filter, theme_filter


def _auto_queue_filter_from_context(context: str) -> str:
    return _auto_queue_filters_from_context(context)[0]


def _is_auto_queue_context(context: str) -> bool:
    return context.startswith("aq_")


def _parse_auto_queue_callback(data: str) -> tuple[str, str, int]:
    parts = data.split(":")
    if len(parts) == 2:
        return "all", "all", int(parts[1])
    if len(parts) >= 4:
        queue_filter = parts[1]
        if queue_filter not in _AUTO_QUEUE_FILTERS:
            queue_filter = "all"
        theme_filter = parts[2]
        if theme_filter not in _QUEUE_THEME_FILTERS:
            theme_filter = "all"
        return queue_filter, theme_filter, int(parts[3])
    if len(parts) >= 3:
        queue_filter = parts[1]
        if queue_filter not in _AUTO_QUEUE_FILTERS:
            queue_filter = "all"
        return queue_filter, "all", int(parts[2])
    return "all", "all", 0


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


def _manual_post_kind_label(kind: str) -> str:
    return str(_MANUAL_POST_TYPES.get(kind, {}).get("label") or kind or "Без типа")


def _manual_post_kind_note(kind: str) -> str:
    return str(_MANUAL_POST_TYPES.get(kind, {}).get("note") or "Редакторский формат без подробного профиля.")


def _manual_post_kind_llm_hint(kind: str) -> str:
    return str(_MANUAL_POST_TYPES.get(kind, {}).get("llm_hint") or "Собери плотный пост по теме пользователя.")


def _manual_post_kind_rubric(kind: str) -> str:
    return str(_MANUAL_POST_TYPES.get(kind, {}).get("rubric") or "manual")


def _manual_post_kind_style_hint(kind: str) -> str:
    return str(_MANUAL_POST_TYPES.get(kind, {}).get("style_hint") or "Тон деловой, плотный и читабельный, без воды и штампов.")


def _manual_theme_label(theme: str) -> str:
    return str(_MANUAL_THEMES.get(theme, {}).get("label") or theme or "Без тематики")


def _manual_theme_note(theme: str) -> str:
    return str(_MANUAL_THEMES.get(theme, {}).get("note") or "Специализированная тематика без дополнительного описания.")


def _manual_theme_rubric(theme: str) -> str:
    return str(_MANUAL_THEMES.get(theme, {}).get("rubric") or "manual")


def _manual_footer_mode_label(kind: str) -> str:
    footer = build_manual_footer(kind)
    if not footer:
        return "без CTA"
    if kind in {"promo_offer", "service_page"}:
        return "продающий CTA"
    return "мягкий CTA"


def _media_preview_label(media_url: str, index: int) -> str:
    if media_url.startswith("tgphoto://"):
        kind = "фото"
    elif media_url.startswith("tgvideo://"):
        kind = "видео"
    elif media_url.startswith("tgdocument://"):
        kind = "документ"
    else:
        kind = "медиа"
    return f"{index}. {kind}"


def _manual_post_kind_structure(kind: str) -> str:
    templates = {
        "promo_offer": "Структура: боль клиента -> решение -> результат -> мягкий CTA.",
        "product_review": "Структура: что это за продукт -> где полезен -> ограничения -> кому подходит.",
        "case_story": "Структура: исходная проблема -> что внедрили -> эффект -> вывод.",
        "opinion": "Структура: тезис -> 2-3 аргумента -> контраргумент -> вывод.",
        "problem_breakdown": "Структура: где узкое место -> почему возникает -> варианты решения -> следующий шаг.",
        "checklist": "Структура: короткий ввод -> 5-7 пунктов чек-листа -> вывод.",
        "faq": "Структура: 4-6 коротких вопросов и ответов по одной теме.",
        "announcement": "Структура: что анонсируем -> для кого -> что получит аудитория.",
        "digest": "Структура: ввод -> 4-6 коротких пунктов -> итоговый вывод.",
        "service_page": "Структура: задача клиента -> что делаем -> результат -> когда это нужно.",
    }
    return templates.get(kind, "Структура: сильный тезис -> прикладное содержание -> завершенный вывод.")


def _manual_post_kind_screen_template(kind: str) -> str:
    templates = {
        "promo_offer": (
            "Опорный шаблон:\n"
            "• Где у клиента рвется процесс\n"
            "• Что именно вы предлагаете изменить\n"
            "• Какой рабочий результат он получает\n"
            "• Какой следующий шаг логичен сейчас"
        ),
        "opinion": (
            "Опорный шаблон:\n"
            "• Жесткий тезис в первой фразе\n"
            "• 2-3 аргумента по существу\n"
            "• Одна оговорка или контраргумент\n"
            "• Спокойный итог для юрфункции или рынка"
        ),
        "case_story": (
            "Опорный шаблон:\n"
            "• Как выглядел процесс до изменений\n"
            "• Что конкретно внедрили или изменили\n"
            "• Где проявился эффект\n"
            "• В каких еще сценариях это применимо"
        ),
        "digest": (
            "Опорный шаблон:\n"
            "• Короткий ввод без воды\n"
            "• 4-6 самостоятельных пунктов\n"
            "• Каждый пункт с отдельной пользой или выводом\n"
            "• В конце один собранный итог"
        ),
        "announcement": (
            "Опорный шаблон:\n"
            "• Что именно запускается или выходит\n"
            "• Для кого это релевантно\n"
            "• Что человек получит на входе/выходе\n"
            "• Что делать, если это ему подходит"
        ),
        "checklist": (
            "Опорный шаблон:\n"
            "• Короткий контекст задачи\n"
            "• 5-7 действий или критериев\n"
            "• Никаких общих слов вместо шага\n"
            "• Финальный вывод: что проверять первым"
        ),
        "faq": (
            "Опорный шаблон:\n"
            "• 4-6 реальных вопросов клиента или руководителя\n"
            "• Короткие, плотные ответы\n"
            "• Один вопрос — один смысловой риск или решение\n"
            "• Финал без повтора FAQ-структуры"
        ),
        "service_page": (
            "Опорный шаблон:\n"
            "• Какую задачу клиента закрывает услуга\n"
            "• Что именно входит в работу\n"
            "• Какой результат получает команда\n"
            "• Когда этот формат особенно уместен"
        ),
        "problem_breakdown": (
            "Опорный шаблон:\n"
            "• Где именно возникает узкое место\n"
            "• Почему оно воспроизводится снова и снова\n"
            "• Какие 2-3 рабочих пути решения есть\n"
            "• С какого шага логично начинать"
        ),
    }
    return templates.get(
        kind,
        (
            "Опорный шаблон:\n"
            "• Один абзац — одна мысль\n"
            "• Без длинной вводной\n"
            "• Финал с ясным выводом"
        ),
    )


def _manual_post_kind_prompt_block(kind: str) -> str:
    prompt_blocks = {
        "promo_offer": (
            "Жесткие правила для рекламного поста:\n"
            "1. Начни с узкого и узнаваемого узкого места клиента, а не с самопрезентации.\n"
            "2. Во втором блоке покажи формат решения: что именно делаем, а не абстрактную пользу.\n"
            "3. В третьем блоке зафиксируй реалистичный результат или эффект без обещаний уровня 'все автоматизируем'.\n"
            "4. Финал должен вести к спокойному следующему шагу: разбор процесса, пилот, аудит, проектирование.\n"
            "5. Запрещены лозунги, крикливые обещания, слова вроде 'революция', 'уникально', 'гарантированно'."
        ),
        "opinion": (
            "Жесткие правила для поста-мнения:\n"
            "1. Первая фраза должна содержать четкий тезис, с которым можно согласиться или спорить.\n"
            "2. Дальше дай 2-3 сильных аргумента, каждый в отдельном коротком абзаце.\n"
            "3. Допустим один контраргумент или оговорка, но без размытия позиции.\n"
            "4. Вывод должен быть взрослым и предметным: что это значит для юрфункции, рынка или руководителя.\n"
            "5. Запрещены нейтральные пересказы новости, банальности и искусственный CTA."
        ),
        "case_story": (
            "Жесткие правила для кейса:\n"
            "1. Сначала зафиксируй исходную проблему или ручной процесс до внедрения.\n"
            "2. Потом покажи, что именно изменили: этап, инструмент, логику маршрута или проверки.\n"
            "3. Затем опиши эффект на языке процесса: скорость, качество, контроль, SLA, снижение рутины, риск-контур.\n"
            "4. Не пиши общих слов вроде 'стало эффективнее' без объяснения, в чем именно это выражается.\n"
            "5. Финал должен содержать практический вывод: где такой сценарий применим еще."
        ),
        "digest": (
            "Жесткие правила для дайджеста:\n"
            "1. Не превращай дайджест в длинную простыню текста.\n"
            "2. Каждый пункт должен жить самостоятельно и содержать отдельную мысль.\n"
            "3. После каждого пункта читатель должен понимать, почему это важно для юрфункции или Legal AI-рынка.\n"
            "4. Пункты не должны повторять друг друга по смыслу.\n"
            "5. Финал должен собрать картину недели или темы в один вывод."
        ),
        "checklist": (
            "Жесткие правила для чек-листа:\n"
            "1. Каждый пункт должен быть проверкой, действием или критерием.\n"
            "2. Запрещены пункты в стиле 'обратить внимание' без уточнения, на что именно.\n"
            "3. Пункты должны идти в рабочем порядке: от базового к более сложному.\n"
            "4. Формулировки должны быть короткими и операционными.\n"
            "5. В конце дай короткий приоритет: с чего начать в первую очередь."
        ),
        "faq": (
            "Жесткие правила для FAQ:\n"
            "1. Вопросы должны звучать так, как их реально задает клиент, GC или руководитель юрфункции.\n"
            "2. Ответ не должен быть длиннее нужного; одна мысль — один ответ.\n"
            "3. В каждом ответе должен быть предметный критерий, риск или рекомендация.\n"
            "4. Запрещены канцелярские ответы и повтор одного и того же тезиса разными словами.\n"
            "5. Финал должен подвести итог, а не просто оборвать список."
        ),
        "announcement": (
            "Жесткие правила для анонса:\n"
            "1. Не начинай с абстрактного 'рады сообщить'. Сразу скажи, что именно запускается.\n"
            "2. Зафиксируй аудиторию: кому это реально нужно.\n"
            "3. Объясни ценность в прикладном виде, а не в лозунгах.\n"
            "4. Финал должен содержать понятное действие: написать, прийти, запросить разбор, открыть материал.\n"
            "5. Убери лишний пафос и корпоративный тон."
        ),
        "service_page": (
            "Жесткие правила для поста об услуге:\n"
            "1. Сначала зафиксируй задачу клиента, а не рассказывай о себе.\n"
            "2. Потом покажи состав работы: аудит, проектирование, настройка, внедрение, сопровождение.\n"
            "3. Результат опиши на языке процесса и управляемости, а не общих обещаний.\n"
            "4. Обязательно обозначь, в каких ситуациях эта услуга действительно нужна.\n"
            "5. Финал должен вести к спокойному следующему шагу без давления."
        ),
        "problem_breakdown": (
            "Жесткие правила для разбора проблемы:\n"
            "1. Разбирай одну конкретную проблему, а не три сразу.\n"
            "2. Назови причину проблемы на уровне процесса, а не только симптом.\n"
            "3. Покажи 2-3 рабочих варианта решения с понятной разницей между ними.\n"
            "4. Не пиши абстрактных советов вроде 'оптимизировать процесс' без конкретики.\n"
            "5. В конце дай приоритет: что делать первым делом."
        ),
    }
    return prompt_blocks.get(
        kind,
        (
            "Общие правила для ручного поста:\n"
            "1. Один абзац — одна мысль.\n"
            "2. Не пиши длинных подводок.\n"
            "3. Заканчивай текст завершенным выводом."
        ),
    )


def _manual_post_kind_from_format_type(format_type: str) -> str:
    normalized = (format_type or "").strip().lower()
    for prefix in ("manual_", "operator_ai_"):
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    return ""


def _post_format_display_label(post: dict[str, Any]) -> str:
    format_type = str(post.get("format_type") or "n/a")
    manual_kind = _manual_post_kind_from_format_type(format_type)
    if manual_kind:
        origin = "✍️" if format_type.startswith("manual_") else "🤖"
        return f"{origin} {_manual_post_kind_label(manual_kind)}"
    return format_type


def _review_origin(format_type: str) -> str:
    normalized = (format_type or "").strip().lower()
    if normalized.startswith("manual_"):
        return "manual"
    return "ai"


def _review_origin_badge(format_type: str) -> str:
    return "✍️" if _review_origin(format_type) == "manual" else "🤖"


def _review_origin_label(review_filter: str) -> str:
    return {
        "all": "Все материалы",
        "ai": "Только AI-драфты",
        "manual": "Только ручные",
    }.get(review_filter, "Все материалы")


def _tg_media_token(message: Message) -> tuple[str, str] | None:
    if message.photo:
        return "photo", f"tgphoto://{message.photo[-1].file_id}"
    if message.video:
        return "video", f"tgvideo://{message.video.file_id}"
    if message.video_note:
        return "video_note", f"tgvideo://{message.video_note.file_id}"
    if message.document:
        mime_type = (message.document.mime_type or "").lower()
        if mime_type.startswith("image/"):
            return "document", f"tgdocument://{message.document.file_id}"
        return None
    return None


def _normalize_transcript_text(text: str) -> str:
    normalized = (text or "").replace("\r", "\n")
    normalized = re.sub(r"\[(?:\d{1,2}:)?\d{1,2}:\d{2}\]", " ", normalized)
    normalized = re.sub(r"\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b", " ", normalized)
    normalized = re.sub(r"(?im)^\s*(спикер\s*\d+|speaker\s*\d+|ведущий|host)\s*:\s*", "", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(
        r"(?i)\b(ну|как бы|в общем|собственно|скажем так|по сути|короче|значит|типа)\b(?:,\s*|\s+)",
        "",
        normalized,
    )
    lines = [line.strip(" -\t") for line in normalized.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


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
        lines.append("")
        lines.append("Это нормально, если сервисы-воркеры не запущены в текущем compose-профиле.")
        lines.append("Воркеры нужны для фоновых задач (например, contract-worker), но для контент-бота могут быть не обязательны.")
        return "\n".join(lines)

    lines.append("")
    for row in workers[:20]:
        worker_id = str(row.get("worker_id") or "unknown")
        active = bool(row.get("active"))
        info = row.get("info") or {}
        mark = "🟢" if active else "⚪"
        display_name = _WORKER_LABELS.get(worker_id, worker_id)
        last_seen = str(row.get("last_seen_at") or "n/a")
        lines.append(f"{mark} {display_name}")
        if display_name != worker_id:
            lines.append(f"   id: {worker_id}")
        slot_times = info.get("slot_times")
        if isinstance(slot_times, list):
            slots = ", ".join(str(item) for item in slot_times if str(item).strip())
            if slots:
                lines.append(f"   слоты: {slots}")
        lines.append(f"   last_seen: {last_seen}")

    return "\n".join(lines)


def _worker_callback_token(worker_id: str) -> str:
    return quote(worker_id, safe="")


def _worker_id_from_callback_token(token: str) -> str:
    return unquote(token or "").strip()


def _worker_list_text(payload: dict[str, Any]) -> str:
    workers = payload.get("workers") or []
    lines = [_format_workers_status(payload), "", "Нажмите на воркер, чтобы открыть активность за последние 24 часа."]
    if not workers:
        lines.append("Когда сервисы начнут слать heartbeat, список и карточки заполнятся автоматически.")
    return "\n".join(lines).strip()


def _format_worker_activity(payload: dict[str, Any]) -> str:
    worker_id = str(payload.get("worker_id") or "unknown")
    display_name = _WORKER_LABELS.get(worker_id, worker_id)
    active = bool(payload.get("active"))
    last_seen = str(payload.get("last_seen_at") or "n/a")
    hours = int(payload.get("window_hours") or 24)
    startup_events = payload.get("startup_events") or []
    action_counts = payload.get("action_counts") or []
    entries = payload.get("entries") or []

    lines = [
        f"Воркер: {display_name}",
        f"ID: {worker_id}",
        f"Статус: {'🟢 активен' if active else '⚪ неактивен'}",
        f"Последний heartbeat: {last_seen}",
        "",
        f"Запуски за {hours} ч: {len(startup_events)}",
    ]
    schedule_lines: list[str] = []
    for row in entries:
        details = row.get("details") or {}
        slot_times = details.get("slot_times")
        if not isinstance(slot_times, list):
            continue
        normalized = ", ".join(str(item) for item in slot_times if str(item).strip())
        if normalized:
            schedule_lines.append(normalized)
    if schedule_lines:
        lines.append(f"Слоты: {schedule_lines[0]}")
        lines.append("")

    if startup_events:
        for row in startup_events[:10]:
            lines.append(f"• {row}")
    else:
        lines.append("• запусков не зафиксировано")

    lines.append("")
    lines.append("Что делал за период:")
    if action_counts:
        for row in action_counts[:10]:
            action = str(row.get("action") or "action")
            count = int(row.get("count") or 0)
            lines.append(f"• {action}: {count}")
    else:
        lines.append("• действий не зафиксировано")

    lines.append("")
    lines.append("Последние события:")
    if entries:
        for row in entries[:12]:
            occurred_at = str(row.get("occurred_at") or "")
            action = str(row.get("action") or "action")
            details = row.get("details") or {}
            detail_line = ""
            if isinstance(details, dict):
                chunks: list[str] = []
                for key in (
                    "slot",
                    "job_id",
                    "result_code",
                    "error",
                    "publish_interval",
                    "limit",
                    "channels",
                    "fetch_limit",
                    "count",
                    "slot_times",
                ):
                    value = details.get(key)
                    if value in (None, "", []):
                        continue
                    chunks.append(f"{key}={value}")
                if chunks:
                    detail_line = " (" + ", ".join(chunks) + ")"
            lines.append(f"• {occurred_at} — {action}{detail_line}")
    else:
        lines.append("• событий пока нет")

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


def _main_menu_markup() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


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
        self._derived_cache: dict[str, tuple[datetime, Any]] = {}

    def _is_admin(self, update: Update) -> bool:
        user = update.effective_user
        return bool(user and user.id in self.admin_ids)

    async def _ensure_admin(self, update: Update) -> bool:
        if self._is_admin(update):
            return True
        message = "Доступ к рабочему столу модератора ограничен."
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

    def _derived_cache_get(self, key: str, *, ttl_seconds: int, force_refresh: bool = False) -> Any | None:
        if force_refresh:
            return None
        cached = self._derived_cache.get(key)
        if cached is None:
            return None
        now = datetime.now(timezone.utc)
        if (now - cached[0]).total_seconds() > ttl_seconds:
            self._derived_cache.pop(key, None)
            return None
        return cached[1]

    def _derived_cache_set(self, key: str, payload: Any) -> None:
        self._derived_cache[key] = (datetime.now(timezone.utc), payload)

    def _invalidate_controls_cache(self) -> None:
        self._controls_cache = None
        self._derived_cache.clear()

    def _invalidate_post_caches(self) -> None:
        self._queue_snapshot_cache = None
        self._posts_cache.clear()
        self._derived_cache.clear()

    def _submenu_nav_rows(self, *, back_callback: str, back_label: str = "🔙 Назад") -> list[list[InlineKeyboardButton]]:
        return [
            [
                _inline_button(back_label, callback_data=back_callback),
                _inline_button("🏠 Рабочий стол", callback_data="refresh"),
            ]
        ]

    @staticmethod
    def _two_column_rows(buttons: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
        rows: list[list[InlineKeyboardButton]] = []
        for index in range(0, len(buttons), 2):
            rows.append(buttons[index : index + 2])
        return rows

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
            error_text = str(exc).lower()
            if "message is not modified" in error_text:
                logger.info("admin_message_not_modified", extra={"callback_data": query.data})
                return False
            if "can't be edited" in error_text or "message to edit not found" in error_text:
                logger.info("admin_message_edit_fallback", extra={"callback_data": query.data, "error": str(exc)})
                if query.message is not None:
                    await query.message.reply_text(text, reply_markup=reply_markup)
                    return True
            raise

    def _controls_map(self, *, force_refresh: bool = False) -> dict[str, bool]:
        rows = self._load_controls(force_refresh=force_refresh)
        return {str(row.get("key") or ""): bool(row.get("enabled", True)) for row in rows}

    def _controls_lookup(self, *, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
        rows = self._load_controls(force_refresh=force_refresh)
        return {str(row.get("key") or ""): row for row in rows if str(row.get("key") or "")}

    def _schedule_config(self, *, force_refresh: bool = False):
        return resolve_schedule_config(self._load_controls(force_refresh=force_refresh))

    def _generate_control_row(self, *, force_refresh: bool = False) -> dict[str, Any]:
        return self._controls_lookup(force_refresh=force_refresh).get("news.generate.enabled", {})

    def _publish_control_row(self, *, force_refresh: bool = False) -> dict[str, Any]:
        return self._controls_lookup(force_refresh=force_refresh).get("news.publish.enabled", {})

    def _telegram_ingest_control_row(self, *, force_refresh: bool = False) -> dict[str, Any]:
        return self._controls_lookup(force_refresh=force_refresh).get("news.telegram_ingest.enabled", {})

    def _configured_generate_interval(self, *, force_refresh: bool = False) -> int:
        row = self._generate_control_row(force_refresh=force_refresh)
        config = row.get("config") or {}
        value = config.get("interval_seconds")
        if isinstance(value, int) and value > 0:
            return value
        return settings.news_generate_interval_seconds

    def _configured_generate_times(self, *, force_refresh: bool = False) -> tuple[str, str]:
        row = self._generate_control_row(force_refresh=force_refresh)
        config = row.get("config") or {}
        morning = str(config.get("morning_time") or settings.news_generate_morning_slot).strip() or settings.news_generate_morning_slot
        evening = str(config.get("evening_time") or settings.news_generate_evening_slot).strip() or settings.news_generate_evening_slot
        return morning, evening

    def _configured_publish_interval(self, *, force_refresh: bool = False) -> int:
        row = self._publish_control_row(force_refresh=force_refresh)
        config = row.get("config") or {}
        value = config.get("interval_seconds")
        if isinstance(value, int) and value > 0:
            return value
        return settings.news_publish_interval_seconds

    def _configured_telegram_ingest_times(self, *, force_refresh: bool = False) -> tuple[str, str]:
        row = self._telegram_ingest_control_row(force_refresh=force_refresh)
        config = row.get("config") or {}
        morning = str(config.get("morning_time") or settings.news_telegram_ingest_morning_slot).strip()
        evening = str(config.get("evening_time") or settings.news_telegram_ingest_evening_slot).strip()
        return (
            morning or settings.news_telegram_ingest_morning_slot,
            evening or settings.news_telegram_ingest_evening_slot,
        )

    def _configured_telegram_fetch_limit(self, *, force_refresh: bool = False) -> int:
        row = self._telegram_ingest_control_row(force_refresh=force_refresh)
        config = row.get("config") or {}
        value = config.get("fetch_limit")
        if isinstance(value, int) and value > 0:
            return max(10, min(value, 200))
        return max(10, min(settings.telegram_fetch_limit, 200))

    def _configured_generate_limit(self, *, force_refresh: bool = False) -> int:
        row = self._generate_control_row(force_refresh=force_refresh)
        config = row.get("config") or {}
        value = config.get("generate_limit")
        if isinstance(value, int) and value > 0:
            return value
        return settings.news_generate_limit

    def _configured_review_retention_days(self, *, force_refresh: bool = False) -> int:
        row = self._generate_control_row(force_refresh=force_refresh)
        config = row.get("config") or {}
        value = config.get("retention_days")
        if isinstance(value, int) and value > 0:
            return value
        return settings.news_review_retention_days

    def _configured_broad_ai_limit(self, *, force_refresh: bool = False) -> int:
        row = self._generate_control_row(force_refresh=force_refresh)
        config = row.get("config") or {}
        value = config.get("broad_ai_limit")
        if isinstance(value, int) and value >= 0:
            return value
        return 1

    def _configured_broad_ai_options(self, *, force_refresh: bool = False) -> list[int]:
        row = self._generate_control_row(force_refresh=force_refresh)
        config = row.get("config") or {}
        raw = config.get("broad_ai_limit_options")
        if isinstance(raw, list):
            options = sorted({int(item) for item in raw if isinstance(item, int) and item >= 0})
            if options:
                return options
        return [0, 1, 2, 3]

    def _enabled_generation_theme_keys(self, *, force_refresh: bool = False) -> set[str]:
        row = self._generate_control_row(force_refresh=force_refresh)
        config = row.get("config") or {}
        raw_enabled = config.get("enabled_themes")
        if isinstance(raw_enabled, list):
            return {str(item).strip() for item in raw_enabled if str(item).strip() in GENERATION_THEME_DEFS}
        return set(generation_theme_keys())

    def _longread_topics_active(self, *, force_refresh: bool = False) -> list[str]:
        schedule = self._schedule_config(force_refresh=force_refresh)
        topics = [item.strip() for item in schedule.longread_topics if str(item).strip()]
        return list(dict.fromkeys(topics))

    def _source_enabled_map(self, *, force_refresh: bool = False) -> dict[str, bool]:
        controls = self._controls_map(force_refresh=force_refresh)
        return {
            key: controls.get(_source_control_key(key), True)
            for key in source_catalog(settings)
        }

    def _controls_text(self, controls: list[dict[str, Any]]) -> str:
        control_map = {str(row.get("key") or ""): bool(row.get("enabled", True)) for row in controls}
        schedule = resolve_schedule_config(controls)
        generate_row = {str(row.get("key") or ""): row for row in controls}.get("news.generate.enabled", {})
        publish_row = {str(row.get("key") or ""): row for row in controls}.get("news.publish.enabled", {})
        generate_config = generate_row.get("config") or {}
        publish_config = publish_row.get("config") or {}
        generate_morning = str(generate_config.get("morning_time") or settings.news_generate_morning_slot).strip() or settings.news_generate_morning_slot
        generate_evening = str(generate_config.get("evening_time") or settings.news_generate_evening_slot).strip() or settings.news_generate_evening_slot
        publish_interval = publish_config.get("interval_seconds") if isinstance(publish_config.get("interval_seconds"), int) else settings.news_publish_interval_seconds
        ingest_row = {str(row.get("key") or ""): row for row in controls}.get("news.telegram_ingest.enabled", {})
        ingest_config = ingest_row.get("config") or {}
        ingest_morning = str(ingest_config.get("morning_time") or settings.news_telegram_ingest_morning_slot).strip() or settings.news_telegram_ingest_morning_slot
        ingest_evening = str(ingest_config.get("evening_time") or settings.news_telegram_ingest_evening_slot).strip() or settings.news_telegram_ingest_evening_slot
        ingest_fetch_limit = (
            ingest_config.get("fetch_limit")
            if isinstance(ingest_config.get("fetch_limit"), int)
            else settings.telegram_fetch_limit
        )
        generate_limit = generate_config.get("generate_limit") if isinstance(generate_config.get("generate_limit"), int) else settings.news_generate_limit
        broad_ai_limit = generate_config.get("broad_ai_limit") if isinstance(generate_config.get("broad_ai_limit"), int) else 1
        retention_days = generate_config.get("retention_days") if isinstance(generate_config.get("retention_days"), int) else settings.news_review_retention_days
        enabled_themes = self._enabled_generation_theme_keys()
        autopilot_enabled = control_map.get("news.generate.enabled", True) and control_map.get(
            "news.publish.enabled", True
        ) and control_map.get(
            "news.telegram_ingest.enabled", True
        )
        feedback_collect = control_map.get("news.feedback.collect.enabled", True)
        feedback_guard = control_map.get("news.feedback.guard.enabled", True)
        discussion_ready = bool((settings.news_discussion_chat_id or "").strip() or (settings.news_discussion_chat_username or "").strip())

        lines = [
            "Автоматизация news",
            "",
            f"Автопилот контента: {'🟢 включен' if autopilot_enabled else '🔴 выключен'}",
            f"Telegram-парсер: {ingest_morning} и {ingest_evening}; лимит канала {ingest_fetch_limit}",
            f"Генерация драфтов: {generate_morning} и {generate_evening}; лимит за цикл {generate_limit}",
            f"Публикация: {_humanize_interval(publish_interval)}",
            f"Хранение драфтов На проверке: {retention_days} дн.",
            f"Broad-AI лимит в цикле: {broad_ai_limit}",
            f"Активных контент-тем: {len(enabled_themes)}/{len(GENERATION_THEME_DEFS)}",
            f"Будни: {schedule_slot_label(schedule.daily_morning_slot)} и {schedule_slot_label(schedule.daily_evening_slot)}",
            f"Обзор недели: {schedule_slot_label(schedule.weekly_review_slot)}",
            f"Лонгрид: {schedule_slot_label(schedule.longread_slot)}",
            f"Юмор: {schedule_slot_label(schedule.humor_slot)}",
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

    def _workspace_text(self, counts: dict[str, int], next_publish: str) -> str:
        return (
            "Рабочий стол редактора\n\n"
            "Это единая стартовая страница модератора: отсюда открываются рабочие списки, календарь, источники, тематики, генерация и автоочередь.\n\n"
            f"📝 Черновики: {counts.get('draft', -1)}\n"
            f"🟡 На проверке: {counts.get('review', -1)}\n"
            f"✅ Готовые: {counts.get('scheduled', -1)}\n"
            f"📤 Опубликованные: {counts.get('posted', -1)}\n"
            f"❌ Ошибки: {counts.get('failed', -1)}\n"
            f"⏳ В публикации: {counts.get('publishing', -1)}\n\n"
            f"Следующая публикация: {next_publish}"
        )

    def _workspace_keyboard(self, counts: dict[str, int]) -> InlineKeyboardMarkup:
        section_buttons = [
            _inline_button("📂 Рабочие списки", callback_data="sec:worklists"),
            _inline_button("⏱ Автоочередь", callback_data="sec:autoqueue"),
            _inline_button("🗓 Календарь", callback_data="cal:summary"),
            _inline_button("📰 Источники", callback_data="sec:sources"),
            _inline_button("🧭 Тематики", callback_data="sec:themes"),
            _inline_button("⚙️ Генерация", callback_data="sec:generate"),
            _inline_button("🛠 Система", callback_data="sec:system"),
            _inline_button("🔄 Обновить", callback_data="refresh"),
        ]
        rows: list[list[InlineKeyboardButton]] = [
            [_inline_button("➕ Создать пост", callback_data="cn:start", style=_BUTTON_STYLE_SUCCESS)],
            *self._two_column_rows(section_buttons),
        ]
        return InlineKeyboardMarkup(rows)

    def _worklists_keyboard(self, counts: dict[str, int]) -> InlineKeyboardMarkup:
        worklist_buttons = [
            _inline_button(f"📝 Черновики ({counts.get('draft', 0)})", callback_data="pl:draft:0"),
            _inline_button(f"🟡 На проверке ({counts.get('review', 0)})", callback_data="rv:all:0"),
            _inline_button(
                f"✅ Готовые ({counts.get('scheduled', 0)})",
                callback_data="pl:scheduled:0",
                style=_BUTTON_STYLE_SUCCESS,
            ),
            _inline_button(f"📤 Опубликованные ({counts.get('posted', 0)})", callback_data="pl:posted:0"),
            _inline_button(
                f"❌ Ошибки ({counts.get('failed', 0)})",
                callback_data="pl:failed:0",
                style=_BUTTON_STYLE_DANGER,
            ),
        ]
        rows = self._two_column_rows(worklist_buttons)
        rows.extend(self._submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
        return InlineKeyboardMarkup(rows)

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

    def _system_text(self, counts: dict[str, int], next_publish: str) -> str:
        return (
            "Система и сервисные функции\n\n"
            "Этот раздел собран для операций, которые раньше были доступны только через slash-команды.\n\n"
            f"📝 Черновики: {counts.get('draft', -1)}\n"
            f"🟡 На проверке: {counts.get('review', -1)}\n"
            f"✅ Готовые: {counts.get('scheduled', -1)}\n"
            f"📤 Опубликованные: {counts.get('posted', -1)}\n"
            f"❌ Ошибки: {counts.get('failed', -1)}\n"
            f"⏳ В публикации: {counts.get('publishing', -1)}\n\n"
            f"Следующая публикация: {next_publish}\n\n"
            "Отсюда доступны: статус API, статус воркеров, глобальная автоматизация, принудительный reset stale и справка.\n"
            "Если воркеры не настроены, раздел «Воркеры» может показывать пустой список."
        )

    def _system_keyboard(self) -> InlineKeyboardMarkup:
        rows = self._two_column_rows(
            [
                _inline_button("📊 Статус API", callback_data="status"),
                _inline_button("👷 Воркеры", callback_data="workers"),
                _inline_button("🤖 Автоматизация", callback_data="automation"),
                _inline_button("❓ Помощь", callback_data="sec:help"),
                _inline_button("🧹 Сброс stale", callback_data="resetstale", style=_BUTTON_STYLE_DANGER),
            ]
        )
        rows.extend(self._submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
        return InlineKeyboardMarkup(rows)

    def _workers_keyboard(self, payload: dict[str, Any]) -> InlineKeyboardMarkup:
        workers = payload.get("workers") or []
        worker_buttons: list[InlineKeyboardButton] = []
        for row in workers[:20]:
            worker_id = str(row.get("worker_id") or "").strip()
            if not worker_id:
                continue
            active = bool(row.get("active"))
            mark = "🟢" if active else "⚪"
            token = _worker_callback_token(worker_id)
            display_name = _WORKER_LABELS.get(worker_id, worker_id)
            worker_buttons.append(_inline_button(f"{mark} {display_name}"[:32], callback_data=f"wrk:{token}"))
        rows = self._two_column_rows(worker_buttons)
        rows.append([_inline_button("🔄 Обновить список", callback_data="workers")])
        rows.extend(self._submenu_nav_rows(back_callback="sec:system", back_label="🔙 К системе"))
        return InlineKeyboardMarkup(rows)

    def _worker_activity_keyboard(self, worker_id: str) -> InlineKeyboardMarkup:
        token = _worker_callback_token(worker_id)
        rows: list[list[InlineKeyboardButton]] = [
            [_inline_button("🔄 Обновить карточку", callback_data=f"wrk:{token}")]
        ]
        rows.extend(self._submenu_nav_rows(back_callback="workers", back_label="🔙 К воркерам"))
        return InlineKeyboardMarkup(rows)

    def _help_text(self) -> str:
        return (
            "Рабочий стол модератора:\n"
            "🏠 Рабочий стол — единый вход в календарь, очереди, источники, тематики и автоматизацию\n"
            "➕ Создать — ручной редактор: тип поста, медиа, материал/транскриб, драфт\n"
            "⏱ Автоочередь — scheduled-посты с фильтрами по виду и теме\n"
            "🗓 Календарь — недельный/месячный обзор и работа с конкретным днем\n"
            "📰 Источники / 🧭 Тематики — контроль discovery-слоя и генерации\n"
            "🤖 Автоматизация — тумблеры, интервалы, слоты и лимиты\n"
            "🛠 Система — статус API, воркеры, reset stale, сервисные функции\n\n"
            "Команды (если нужно):\n"
            "/start, /admin, /newpost, /generate_now, /calendar, /help"
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
        rows.extend(self._submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
        return InlineKeyboardMarkup(rows)

    def _source_stats(self, *, force_refresh: bool = False) -> dict[str, dict[str, int]]:
        cache_key = "source_stats"
        cached = self._derived_cache_get(cache_key, ttl_seconds=_DERIVED_CACHE_TTL_SECONDS, force_refresh=force_refresh)
        if cached is not None:
            return {key: dict(value) for key, value in cached.items()}

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
        self._derived_cache_set(cache_key, {key: dict(value) for key, value in stats.items()})
        return stats

    def _telegram_channel_enabled_map(self, force_refresh: bool = False) -> dict[str, bool]:
        controls = self._controls_map(force_refresh=force_refresh)
        result: dict[str, bool] = {}
        for channel in settings.telegram_channels_list:
            slug = _telegram_channel_slug(channel)
            result[slug] = controls.get(_telegram_channel_control_key(slug), True)
        return result

    def _telegram_channel_history_counts(self, *, force_refresh: bool = False) -> dict[str, dict[str, int]]:
        cache_key = "telegram_channel_history_counts"
        cached = self._derived_cache_get(cache_key, ttl_seconds=_DERIVED_CACHE_TTL_SECONDS, force_refresh=force_refresh)
        if cached is not None:
            return {key: dict(value) for key, value in cached.items()}

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
        self._derived_cache_set(cache_key, {key: dict(value) for key, value in stats.items()})
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
        rows.extend(self._submenu_nav_rows(back_callback="sec:sources", back_label="🔙 К источникам"))
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
                [
                    _inline_button("🔙 К Telegram Channels", callback_data="srd:telegram_channels"),
                    _inline_button("🏠 Рабочий стол", callback_data="refresh"),
                ],
            ]
        )

    def _load_source_posts(self, source_key: str, offset: int, *, force_refresh: bool = False) -> tuple[int, list[dict[str, Any]]]:
        cache_key = f"source_posts:{source_key}"
        filtered = self._derived_cache_get(cache_key, ttl_seconds=_DERIVED_CACHE_TTL_SECONDS, force_refresh=force_refresh)
        if filtered is None:
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
            self._derived_cache_set(cache_key, list(filtered))
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
            publication_kind = self._publication_kind(row)
            lines.append(f"{idx}. {status_badge} {publication_kind_badge(publication_kind)} {title[:80]}")
            lines.append(f"   ⏰ {publish_at} | {publication_kind_label(publication_kind)}")
        return "\n".join(lines)

    def _source_posts_keyboard(self, source_key: str, total: int, rows: list[dict[str, Any]], offset: int) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            status = str(row.get("status") or "scheduled")
            publication_kind = self._publication_kind(row)
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{idx}. {_status_badge(status)} {publication_kind_badge(publication_kind)} {title[:40]}",
                        callback_data=f"pv:{post_id}:src_{source_key}:{offset}",
                    )
                ]
            )

        nav: list[InlineKeyboardButton] = []
        prev_offset = max(0, offset - _POSTS_PAGE_SIZE)
        next_offset = offset + _POSTS_PAGE_SIZE
        if offset > 0:
            nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"src:{source_key}:{prev_offset}"))
        if next_offset < total:
            nav.append(InlineKeyboardButton("➡️ Далее", callback_data=f"src:{source_key}:{next_offset}"))
        if nav:
            buttons.append(nav)
        buttons.extend(self._submenu_nav_rows(back_callback="sec:sources", back_label="🔙 К источникам"))
        return InlineKeyboardMarkup(buttons)

    def _generation_theme_stats(self, *, force_refresh: bool = False) -> dict[str, int]:
        cache_key = "generation_theme_stats"
        cached = self._derived_cache_get(cache_key, ttl_seconds=_DERIVED_CACHE_TTL_SECONDS, force_refresh=force_refresh)
        if cached is not None:
            return dict(cached)

        counts: dict[str, int] = {theme_key: 0 for theme_key in GENERATION_THEME_DEFS}
        for status in ("review", "scheduled", "posted", "failed"):
            for row in self._list_posts_rows(status=status, newest_first=True, limit=100):
                title = str(row.get("title") or "")
                text = str(row.get("text") or "")
                for theme_key in generation_themes_for_text(f"{title}\n{text}"):
                    counts[theme_key] = counts.get(theme_key, 0) + 1
        self._derived_cache_set(cache_key, dict(counts))
        return counts

    def _theme_stats(self, *, force_refresh: bool = False) -> dict[str, int]:
        cache_key = "theme_stats"
        cached = self._derived_cache_get(cache_key, ttl_seconds=_DERIVED_CACHE_TTL_SECONDS, force_refresh=force_refresh)
        if cached is not None:
            return dict(cached)

        counts: dict[str, int] = {pillar: 0 for pillar in _PILLAR_LABELS}
        for status in ("review", "scheduled", "posted", "failed"):
            for row in self._list_posts_rows(status=status, newest_first=True, limit=100):
                title = str(row.get("title") or "")
                text = str(row.get("text") or "")
                pillar = normalize_rubric_to_pillar(row.get("rubric"), f"{title}\n{text}")
                counts[pillar] = counts.get(pillar, 0) + 1
        self._derived_cache_set(cache_key, dict(counts))
        return counts

    def _themes_text(self, counts: dict[str, int], generation_counts: dict[str, int] | None = None) -> str:
        generation_counts = generation_counts or self._generation_theme_stats()
        enabled_generation_themes = self._enabled_generation_theme_keys()
        active_longread_topics = self._longread_topics_active()
        total_archive = sum(max(0, int(value)) for value in counts.values())
        return (
            "Тематики контента\n\n"
            "Раздел теперь разделен на 3 отдельных блока:\n"
            "1) 🗞 Ежедневные/регулярные посты (темы автогенерации)\n"
            "2) 📚 Воскресные лонгриды (отдельный пул тем)\n"
            "3) 🗂 Архивные корзины (уже созданные посты)\n\n"
            f"Активно ежедневных тем: {len(enabled_generation_themes)}/{len(generation_counts)}\n"
            f"Активно тем лонгридов: {len(active_longread_topics)}/{len(_LONGREAD_TOPIC_LIBRARY)}\n"
            f"Постов в архивных корзинах: {total_archive}\n\n"
            "Выберите нужный блок кнопками ниже."
        )

    def _themes_keyboard(self, counts: dict[str, int], generation_counts: dict[str, int] | None = None) -> InlineKeyboardMarkup:
        _ = counts, generation_counts
        rows: list[list[InlineKeyboardButton]] = [
            [
                _inline_button("🗞 Ежедневные темы", callback_data="thm:daily"),
                _inline_button("📚 Лонгриды", callback_data="lt:menu"),
            ],
            [_inline_button("🗂 Архивные корзины", callback_data="thm:archive")],
        ]
        rows.extend(self._submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
        return InlineKeyboardMarkup(rows)

    def _themes_daily_text(self, generation_counts: dict[str, int] | None = None) -> str:
        generation_counts = generation_counts or self._generation_theme_stats()
        enabled_generation_themes = self._enabled_generation_theme_keys()
        lines = [
            "Ежедневные/регулярные темы автогенерации",
            "",
            "Эти тумблеры влияют на генерацию ежедневных постов, обзоров недели и юмора.",
            "Воскресный лонгрид настраивается отдельно в разделе «Лонгриды».",
            "",
        ]
        for theme_key in generation_theme_keys():
            mark = "✅" if theme_key in enabled_generation_themes else "☐"
            lines.append(
                f"• {mark} {generation_theme_label(theme_key)} — {generation_counts.get(theme_key, 0)}"
            )
            lines.append(f"  {generation_theme_note(theme_key)}")
        return "\n".join(lines)

    def _themes_daily_keyboard(self, generation_counts: dict[str, int] | None = None) -> InlineKeyboardMarkup:
        generation_counts = generation_counts or self._generation_theme_stats()
        enabled_generation_themes = self._enabled_generation_theme_keys()
        rows: list[list[InlineKeyboardButton]] = []
        for theme_key in generation_theme_keys():
            rows.append(
                [
                    _inline_button(
                        f"{'✅' if theme_key in enabled_generation_themes else '☐'} {generation_theme_label(theme_key)} ({generation_counts.get(theme_key, 0)})"[:56],
                        callback_data=f"gt:{theme_key}",
                    )
                ]
            )
        rows.append([_inline_button("📚 Открыть темы лонгридов", callback_data="lt:menu")])
        rows.extend(self._submenu_nav_rows(back_callback="sec:themes", back_label="🔙 К блокам тематик"))
        return InlineKeyboardMarkup(rows)

    def _themes_archive_text(self, counts: dict[str, int]) -> str:
        target_share = {
            "regulation": "30%",
            "case": "20%",
            "implementation": "30%",
            "tools": "15%",
            "market": "5%",
        }
        lines = [
            "Архивные корзины публикаций",
            "",
            "Здесь только уже созданные посты (на проверке / готовые / опубликованные / ошибки).",
            "Нажмите на корзину, чтобы открыть список постов по тематике.",
            "",
        ]
        for pillar, label in _PILLAR_LABELS.items():
            rubric_labels = ", ".join(_rubric_label(item) for item in _PILLAR_RUBRICS.get(pillar, ()))
            lines.append(
                f"• {_pillar_badge(pillar)} {label}: {counts.get(pillar, 0)} пост(ов), целевая доля {target_share.get(pillar, 'n/a')}"
            )
            if rubric_labels:
                lines.append(f"  Рубрики: {rubric_labels}")
        return "\n".join(lines)

    def _themes_archive_keyboard(self, counts: dict[str, int]) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = self._two_column_rows(
            [
                _inline_button(f"{_pillar_display(pillar)} ({counts.get(pillar, 0)})"[:40], callback_data=f"th:{pillar}:0")
                for pillar in _PILLAR_LABELS
            ]
        )
        rows.extend(self._submenu_nav_rows(back_callback="sec:themes", back_label="🔙 К блокам тематик"))
        return InlineKeyboardMarkup(rows)

    def _load_theme_posts(self, pillar: str, offset: int, *, force_refresh: bool = False) -> tuple[int, list[dict[str, Any]]]:
        cache_key = f"theme_posts:{pillar}"
        filtered = self._derived_cache_get(cache_key, ttl_seconds=_DERIVED_CACHE_TTL_SECONDS, force_refresh=force_refresh)
        if filtered is None:
            rows: list[dict[str, Any]] = []
            for status in ("review", "scheduled", "posted", "failed"):
                rows.extend(self._list_posts_rows(status=status, newest_first=True, limit=100))
            filtered = []
            for row in rows:
                title = str(row.get("title") or "")
                text = str(row.get("text") or "")
                row_pillar = normalize_rubric_to_pillar(row.get("rubric"), f"{title}\n{text}")
                if row_pillar == pillar:
                    filtered.append(row)
            self._derived_cache_set(cache_key, list(filtered))
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
            publication_kind = self._publication_kind(row)
            lines.append(f"{idx}. {status_badge} {publication_kind_badge(publication_kind)} {title[:82]}")
            lines.append(f"   Рубрика: {rubric} | {publication_kind_label(publication_kind)}")
        return "\n".join(lines)

    def _theme_posts_keyboard(self, pillar: str, total: int, rows: list[dict[str, Any]], offset: int) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            status = str(row.get("status") or "scheduled")
            publication_kind = self._publication_kind(row)
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{idx}. {_status_badge(status)} {publication_kind_badge(publication_kind)} {title[:40]}",
                        callback_data=f"pv:{post_id}:th_{pillar}:{offset}",
                    )
                ]
            )

        nav: list[InlineKeyboardButton] = []
        prev_offset = max(0, offset - _POSTS_PAGE_SIZE)
        next_offset = offset + _POSTS_PAGE_SIZE
        if offset > 0:
            nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"th:{pillar}:{prev_offset}"))
        if next_offset < total:
            nav.append(InlineKeyboardButton("➡️ Далее", callback_data=f"th:{pillar}:{next_offset}"))
        if nav:
            buttons.append(nav)
        buttons.extend(self._submenu_nav_rows(back_callback="sec:themes", back_label="🔙 К тематикам"))
        return InlineKeyboardMarkup(buttons)

    def _generation_text(self, controls: dict[str, bool]) -> str:
        source_count = len(resolve_source_urls(settings, enabled_overrides=self._source_enabled_map()))
        schedule = self._schedule_config()
        generate_morning, generate_evening = self._configured_generate_times()
        telegram_morning, telegram_evening = self._configured_telegram_ingest_times()
        telegram_fetch_limit = self._configured_telegram_fetch_limit()
        publish_interval = self._configured_publish_interval()
        generate_limit = self._configured_generate_limit()
        broad_ai_limit = self._configured_broad_ai_limit()
        retention_days = self._configured_review_retention_days()
        discussion_ready = bool((settings.news_discussion_chat_id or "").strip() or (settings.news_discussion_chat_username or "").strip())
        telegram_channel_count = len(self._telegram_channel_enabled_map())
        return (
            "Ручная генерация\n\n"
            f"Telegram-парсер: {'🟢' if controls.get('news.telegram_ingest.enabled', True) else '🔴'}\n"
            f"Автогенерация: {'🟢' if controls.get('news.generate.enabled', True) else '🔴'}\n"
            f"Автопубликация: {'🟢' if controls.get('news.publish.enabled', True) else '🔴'}\n"
            f"Feedback guard: {'🟢' if controls.get('news.feedback.guard.enabled', True) else '🔴'}\n\n"
            f"Слоты Telegram-парсера: {telegram_morning} и {telegram_evening}\n"
            f"Лимит Telegram-парсера: {telegram_fetch_limit} сообщений/канал\n"
            f"Слоты автогенерации: {generate_morning} и {generate_evening}\n"
            f"Интервал автопубликации: {_humanize_interval(publish_interval)}\n"
            f"Лимит генерации за цикл: {generate_limit}\n"
            f"Broad-AI лимит за цикл: {broad_ai_limit}\n"
            f"Хранение в «На проверке»: {retention_days} дн.\n"
            f"Источников RSS/search: {source_count}\n"
            f"Telegram-каналов: {telegram_channel_count}\n"
            f"Будни: {schedule_slot_label(schedule.daily_morning_slot)} и {schedule_slot_label(schedule.daily_evening_slot)}\n"
            f"Обзор недели: пятница {schedule_slot_label(schedule.weekly_review_slot)}\n"
            f"Лонгрид: воскресенье {schedule_slot_label(schedule.longread_slot)}\n"
            f"Юмор: суббота {schedule_slot_label(schedule.humor_slot)}\n\n"
            f"Комментарии/feedback: {'🟢 linked discussion group указана в контуре' if discussion_ready else '🟡 треды в Telegram могут работать, но для сбора feedback нужно указать linked discussion group в env'}\n\n"
            "Контур ограничен темами Legal AI, автоматизации юрфункции, legal tech и AI-регулирования.\n"
            "Общие AI-новости без связи с юридической функцией должны отсеиваться на этапе отбора.\n\n"
            "Ниже запускается подбор кандидатов. Все найденные AI-драфты сразу создаются как реальные посты в статусе «На проверке», без временных preview-списков."
        )

    def _generation_keyboard(self, preview_count: int = 0) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                _inline_button("⚡ Сгенерировать 3", callback_data="gen:pick:3", style=_BUTTON_STYLE_SUCCESS),
                _inline_button("⚡ Сгенерировать 5", callback_data="gen:pick:5", style=_BUTTON_STYLE_SUCCESS),
            ],
            [
                _inline_button("⚡ Сгенерировать 10", callback_data="gen:pick:10", style=_BUTTON_STYLE_SUCCESS),
            ],
        ]
        rows.extend(
            [
                [
                    _inline_button("🟡 На проверке", callback_data="rv:all:0"),
                    _inline_button("📰 Источники", callback_data="sec:sources"),
                ],
                [
                    _inline_button("🧭 Тематики", callback_data="sec:themes"),
                    _inline_button("🕒 Время слотов", callback_data="sch:menu"),
                ],
                [_inline_button("⏱ Ритм", callback_data="int:menu")],
            ]
        )
        rows.extend(self._submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
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
                f"Вид публикации: {publication_kind_label(str(preview.get('publication_kind') or publication_kind_from_format_type(str(preview.get('format_type') or ''))))}",
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
        rows.extend(self._submenu_nav_rows(back_callback="sec:generate", back_label="🔙 К генерации"))
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
        buttons.extend(self._submenu_nav_rows(back_callback="sec:generate", back_label="🔙 К генерации"))
        return InlineKeyboardMarkup(buttons)

    def _automation_keyboard(self, controls: list[dict[str, Any]]) -> InlineKeyboardMarkup:
        control_map = {str(row.get("key") or ""): bool(row.get("enabled", True)) for row in controls}
        full_automation_enabled = (
            control_map.get("news.generate.enabled", True)
            and control_map.get("news.telegram_ingest.enabled", True)
            and control_map.get("news.publish.enabled", True)
        )
        rows: list[list[InlineKeyboardButton]] = [
            [
                _inline_button(
                    "🟢 Полная автоматизация" if not full_automation_enabled else "⛔ Полная автоматизация",
                    callback_data=f"fa:{'1' if not full_automation_enabled else '0'}",
                    style=_BUTTON_STYLE_SUCCESS if not full_automation_enabled else _BUTTON_STYLE_DANGER,
                ),
            ],
            [
                _inline_button("🧰 Пресет 2х/день (5,3д)", callback_data="preset:twice_daily"),
            ],
            [
                _inline_button("🗓 Сетка публикаций", callback_data="sch:menu"),
                _inline_button("📚 Темы лонгридов", callback_data="lt:menu"),
            ],
            [
                _inline_button("🧭 Темы генерации", callback_data="sec:themes"),
                _inline_button("📰 Источники", callback_data="sec:sources"),
            ],
            [
                _inline_button("✅ Включить всё", callback_data="all:1", style=_BUTTON_STYLE_SUCCESS),
                _inline_button("⛔ Отключить всё", callback_data="all:0", style=_BUTTON_STYLE_DANGER),
            ],
            [_inline_button("🧹 Сброс stale", callback_data="resetstale", style=_BUTTON_STYLE_DANGER)],
        ]
        control_buttons: list[InlineKeyboardButton] = []
        for row in controls:
            key = str(row.get("key") or "")
            enabled = _is_enabled(row.get("enabled", True))
            next_value = "0" if enabled else "1"
            icon = "🟢" if enabled else "🔴"
            title = str(row.get("title") or key)
            button_text = f"{icon} {title}"
            control_buttons.append(
                _inline_button(
                    button_text[:34],
                    callback_data=f"set:{key}:{next_value}",
                    style=_BUTTON_STYLE_SUCCESS if not enabled else _BUTTON_STYLE_DANGER,
                )
            )
        rows.extend(self._two_column_rows(control_buttons))
        rows.extend(self._submenu_nav_rows(back_callback="sec:system", back_label="🔙 К системе"))
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

    def _publication_kind(self, row: dict[str, Any]) -> str:
        return publication_kind_from_format_type(str(row.get("format_type") or ""))

    def _row_pillar(self, row: dict[str, Any]) -> str:
        title = str(row.get("title") or "")
        text = _strip_html_markup(str(row.get("text") or ""))
        return normalize_rubric_to_pillar(row.get("rubric"), f"{title}\n{text}")

    def _load_auto_queue(self, queue_filter: str, offset: int, theme_filter: str = "all") -> tuple[int, list[dict[str, Any]], int]:
        rows = self._list_posts_rows(status="scheduled", newest_first=False, limit=100)
        overdue = self._overdue_scheduled_count()
        if queue_filter != "all":
            rows = [row for row in rows if self._publication_kind(row) == queue_filter]
        if theme_filter != "all":
            rows = [row for row in rows if self._row_pillar(row) == theme_filter]
        total = len(rows)
        return total, rows[offset : offset + _POSTS_PAGE_SIZE], overdue

    def _auto_queue_text(
        self,
        total: int,
        rows: list[dict[str, Any]],
        offset: int,
        overdue: int,
        queue_filter: str,
        theme_filter: str = "all",
    ) -> str:
        tz = ZoneInfo(settings.tz_name)
        schedule = self._schedule_config()
        filter_label = "Все публикации" if queue_filter == "all" else publication_kind_label(queue_filter)
        theme_label = "Все темы" if theme_filter == "all" else _pillar_display(theme_filter)
        generate_morning, generate_evening = self._configured_generate_times()
        publish_interval = self._configured_publish_interval()
        lines = [
            "Автоочередь публикации",
            "",
            f"Фильтр: {filter_label}",
            f"Тема: {theme_label}",
            f"Автогенерация: {generate_morning} и {generate_evening}",
            f"Автопубликация: {_humanize_interval(publish_interval)}",
            f"Всего scheduled: {total}",
            f"Просрочено: {overdue}",
            "",
            "Текущая сетка:",
            f"• Пн-Пт: {schedule_slot_label(schedule.daily_morning_slot)} и {schedule_slot_label(schedule.daily_evening_slot)}",
            f"• Пятница: обзор недели в {schedule_slot_label(schedule.weekly_review_slot)}",
            f"• Суббота: юмор в {schedule_slot_label(schedule.humor_slot)}",
            f"• Воскресенье: лонгрид в {schedule_slot_label(schedule.longread_slot)}",
            "",
        ]
        if not rows:
            lines.append("В scheduled сейчас нет постов.")
            return "\n".join(lines)

        current_day = ""
        for idx, row in enumerate(rows, start=offset + 1):
            publish_at = self._publish_at_utc(row)
            if publish_at is None:
                continue
            local_dt = publish_at.astimezone(tz)
            day_label = local_dt.strftime("%Y-%m-%d")
            if day_label != current_day:
                current_day = day_label
                lines.extend(["", day_label])
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            kind = self._publication_kind(row)
            pillar = self._row_pillar(row)
            format_label = _post_format_display_label(row)
            lines.append(
                f"{idx}. {local_dt.strftime('%H:%M')} {publication_kind_badge(kind)} {publication_kind_label(kind)} — {title[:68]}"
            )
            lines.append(f"   🧭 {_pillar_label(pillar)} | {format_label}")
        return "\n".join(lines)

    def _auto_queue_keyboard(
        self,
        total: int,
        rows: list[dict[str, Any]],
        offset: int,
        queue_filter: str,
        theme_filter: str = "all",
    ) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        filter_rows = [
            ("all", "Все"),
            ("daily", "Ежедневные"),
            ("weekly_review", "Обзоры"),
            ("longread", "Лонгриды"),
            ("humor", "Юмор"),
            ("other", "Прочее"),
        ]
        for index in range(0, len(filter_rows), 2):
            chunk = filter_rows[index : index + 2]
            buttons.append(
                [
                    _inline_button(
                        f"{'• ' if queue_filter == item_key else ''}{item_label}",
                        callback_data=f"aq:{item_key}:{theme_filter}:0",
                    )
                    for item_key, item_label in chunk
                ]
            )
        theme_rows = [("all", "Все темы")] + [(pillar, _pillar_display(pillar)) for pillar in _PILLAR_LABELS]
        for index in range(0, len(theme_rows), 2):
            chunk = theme_rows[index : index + 2]
            buttons.append(
                [
                    _inline_button(
                        f"{'• ' if theme_filter == item_key else ''}{item_label}",
                        callback_data=f"aq:{queue_filter}:{item_key}:0",
                    )
                    for item_key, item_label in chunk
                ]
            )
        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            kind = self._publication_kind(row)
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{idx}. {publication_kind_badge(kind)} {title[:40]}",
                        callback_data=f"pv:{post_id}:{_auto_queue_context(queue_filter, theme_filter)}:{offset}",
                    )
                ]
            )

        nav: list[InlineKeyboardButton] = []
        prev_offset = max(0, offset - _POSTS_PAGE_SIZE)
        next_offset = offset + _POSTS_PAGE_SIZE
        if offset > 0:
            nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"aq:{queue_filter}:{theme_filter}:{prev_offset}"))
        if next_offset < total:
            nav.append(InlineKeyboardButton("➡️ Далее", callback_data=f"aq:{queue_filter}:{theme_filter}:{next_offset}"))
        if nav:
            buttons.append(nav)
        buttons.append(
            [
                _inline_button("🗓 Календарь", callback_data="cal:summary"),
                _inline_button("🕒 Время слотов", callback_data="sch:menu"),
            ]
        )
        buttons.append(
            [
                _inline_button("⏱ Ритм", callback_data="int:menu"),
                _inline_button("🔄 Обновить", callback_data=f"aq:{queue_filter}:{theme_filter}:{offset}"),
            ]
        )
        buttons.extend(self._submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
        return InlineKeyboardMarkup(buttons)

    async def _panel_text(self, controls: list[dict[str, Any]]) -> str:
        counts, next_publish = await self._queue_snapshot()
        control_map = {str(row.get("key") or ""): bool(row.get("enabled", True)) for row in controls}
        generate_morning, generate_evening = self._configured_generate_times()
        telegram_morning, telegram_evening = self._configured_telegram_ingest_times()
        publish_interval = self._configured_publish_interval()
        generate_limit = self._configured_generate_limit()
        retention_days = self._configured_review_retention_days()
        lines = [
            "Рабочий стол модератора Legal AI PRO",
            "",
            f"Автопилот: {'🟢' if control_map.get('news.generate.enabled', True) and control_map.get('news.telegram_ingest.enabled', True) and control_map.get('news.publish.enabled', True) else '🔴'}",
            f"Telegram-парсер: {telegram_morning} и {telegram_evening}",
            f"Автогенерация: {generate_morning} и {generate_evening}; лимит {generate_limit}",
            f"Автопубликация: {_humanize_interval(publish_interval)}",
            f"Хранение На проверке: {retention_days} дн.",
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
            "Ниже открываются ключевые разделы редактора. Рабочий стол является единственной стартовой точкой входа.",
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

    def _load_manual_queue(self, queue_filter: str, offset: int, theme_filter: str = "all") -> tuple[int, list[dict[str, Any]], int, int]:
        all_rows = self._list_posts_rows(status="scheduled", newest_first=False, limit=100)
        now_utc = datetime.now(timezone.utc)
        due_rows = [row for row in all_rows if (publish_at := self._publish_at_utc(row)) and publish_at <= now_utc]
        filtered_rows = due_rows if queue_filter == "due" else all_rows
        if theme_filter != "all":
            filtered_rows = [row for row in filtered_rows if self._row_pillar(row) == theme_filter]
        total = len(filtered_rows)
        return total, filtered_rows[offset : offset + _POSTS_PAGE_SIZE], len(due_rows), len(all_rows)

    def _scheduled_rows_by_day(self, *, force_refresh: bool = False) -> dict[str, list[dict[str, Any]]]:
        cache_key = "scheduled_rows_by_day"
        cached = self._derived_cache_get(cache_key, ttl_seconds=_CALENDAR_CACHE_TTL_SECONDS, force_refresh=force_refresh)
        if cached is not None:
            return cached

        tz = ZoneInfo(settings.tz_name)
        rows = self._list_posts_rows(status="scheduled", newest_first=False, limit=100)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            publish_at = self._publish_at_utc(row)
            if publish_at is None:
                continue
            day_key = publish_at.astimezone(tz).date().isoformat()
            grouped.setdefault(day_key, []).append(row)
        for day_key in grouped:
            grouped[day_key].sort(
                key=lambda item: self._publish_at_utc(item) or datetime.max.replace(tzinfo=timezone.utc)
            )
        self._derived_cache_set(cache_key, grouped)
        return grouped

    def _scheduled_rows_for_day(self, day_key: str, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        grouped = self._scheduled_rows_by_day(force_refresh=force_refresh)
        return list(grouped.get(day_key, []))

    def _calendar_groups(self, *, force_refresh: bool = False) -> list[tuple[str, list[Any]]]:
        cache_key = "calendar_groups"
        cached = self._derived_cache_get(cache_key, ttl_seconds=_CALENDAR_CACHE_TTL_SECONDS, force_refresh=force_refresh)
        if cached is not None:
            return cached

        tz = ZoneInfo(settings.tz_name)
        now_local = datetime.now(tz)
        grouped: dict[str, list[Any]] = {}
        for slot in build_schedule_window(now_local, days=14, control_rows=self._load_controls(), future_only=True):
            grouped.setdefault(slot.day.isoformat(), []).append(slot)
        result = sorted(grouped.items(), key=lambda item: item[0])
        self._derived_cache_set(cache_key, result)
        return result

    def _overdue_scheduled_count(self) -> int:
        rows = self._list_posts_rows(status="scheduled", newest_first=False, limit=100)
        now_utc = datetime.now(timezone.utc)
        return sum(1 for row in rows if (publish_at := self._publish_at_utc(row)) and publish_at < now_utc)

    def _calendar_summary_text(self, groups: list[tuple[str, list[dict[str, Any]]]]) -> str:
        overdue_count = self._overdue_scheduled_count()
        scheduled_by_day = self._scheduled_rows_by_day()
        schedule = self._schedule_config()
        generate_morning, generate_evening = self._configured_generate_times()
        publish_interval = self._configured_publish_interval()
        generate_limit = self._configured_generate_limit()
        retention_days = self._configured_review_retention_days()
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
        lines = [
            "Календарь автопубликаций",
            "",
            "Редакционная сетка:",
            f"• Ежедневные по будням: {schedule_slot_label(schedule.daily_morning_slot)} и {schedule_slot_label(schedule.daily_evening_slot)}",
            f"• Обзор недели: пятница {schedule_slot_label(schedule.weekly_review_slot)}",
            f"• Лонгрид: воскресенье {schedule_slot_label(schedule.longread_slot)}",
            f"• Юмор: суббота {schedule_slot_label(schedule.humor_slot)}",
            "",
            "Ритм автопилота:",
            f"• Генерация: {generate_morning} и {generate_evening}",
            f"• Публикация: {_humanize_interval(publish_interval)}",
            f"• Лимит за цикл: {generate_limit}",
            f"• Хранение драфтов: {retention_days} дн.",
            "",
        ]
        if overdue_count:
            lines.append(f"Просроченных scheduled-постов: {overdue_count}")
            lines.append("Они вынесены из календаря текущих дат. Для работы с ними используйте ручную очередь.")
            lines.append("")
        for day_key, slots in groups[:10]:
            day_date = datetime.fromisoformat(day_key).date()
            if day_date == now_local:
                day_label = f"{day_key} (сегодня)"
            elif day_date == now_local + timedelta(days=1):
                day_label = f"{day_key} (завтра)"
            else:
                day_label = day_key
            scheduled_rows = scheduled_by_day.get(day_key, [])
            slot_labels = ", ".join(
                f"{slot.publish_at_local.strftime('%H:%M')} {publication_kind_badge(slot.publication_kind)}"
                for slot in slots
            )
            lines.append(
                f"• {day_label}: {slot_labels} | занято {min(len(scheduled_rows), len(slots))}/{len(slots)}"
            )
        return "\n".join(lines)

    def _calendar_month_text(self, groups: list[tuple[str, list[dict[str, Any]]]]) -> str:
        overdue_count = self._overdue_scheduled_count()
        scheduled_by_day = self._scheduled_rows_by_day()
        schedule = self._schedule_config()
        lines = [
            "Календарь автопубликаций — месячный вид",
            "",
            "Сетка:",
            f"• Будни: {schedule_slot_label(schedule.daily_morning_slot)} и {schedule_slot_label(schedule.daily_evening_slot)}",
            f"• Пятница: обзор недели в {schedule_slot_label(schedule.weekly_review_slot)}",
            f"• Суббота: юмор в {schedule_slot_label(schedule.humor_slot)}",
            f"• Воскресенье: лонгрид в {schedule_slot_label(schedule.longread_slot)}",
            "",
        ]
        if overdue_count:
            lines.append(f"⚠️ Просроченных scheduled-постов: {overdue_count}")
            lines.append("")
        month_groups = groups[:28]
        if not month_groups:
            lines.append("На ближайшие недели слотов нет.")
            return "\n".join(lines)
        for day_key, slots in month_groups:
            day_date = datetime.fromisoformat(day_key).date()
            slot_badges = " ".join(publication_kind_badge(slot.publication_kind) for slot in slots)
            scheduled_rows = scheduled_by_day.get(day_key, [])
            lines.append(
                f"• {day_date.strftime('%d.%m')} | {slot_badges} | занято {min(len(scheduled_rows), len(slots))}/{len(slots)}"
            )
        return "\n".join(lines)

    def _calendar_summary_keyboard(self, groups: list[tuple[str, list[Any]]], view: str = "week") -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        tz = ZoneInfo(settings.tz_name)
        now_local = datetime.now(tz).date()
        overdue_count = self._overdue_scheduled_count()
        buttons.append(
            [
                _inline_button(f"{'• ' if view == 'day' else ''}День", callback_data=f"cal:view:day:{now_local.isoformat()}"),
                _inline_button(f"{'• ' if view == 'week' else ''}Неделя", callback_data="cal:summary"),
                _inline_button(f"{'• ' if view == 'month' else ''}Месяц", callback_data="cal:view:month"),
            ]
        )
        if view == "day":
            day_key = now_local.isoformat()
            buttons.append([InlineKeyboardButton("📅 Открыть расписание на сегодня", callback_data=f"cal:day:{day_key}")])
            if overdue_count:
                buttons.append([InlineKeyboardButton(f"⚠️ Просрочено ({overdue_count})", callback_data="aq:all:all:0")])
            buttons.append(
                [
                    InlineKeyboardButton("🕒 Время слотов", callback_data="sch:menu"),
                    InlineKeyboardButton("⏱ Ритм генерации", callback_data="int:menu"),
                ]
            )
            buttons.append([InlineKeyboardButton("🔄 Обновить календарь", callback_data=f"cal:view:day:{day_key}")])
            buttons.extend(self._submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
            return InlineKeyboardMarkup(buttons)

        row_buffer: list[InlineKeyboardButton] = []
        max_days = 8 if view == "week" else 28
        max_columns = 2 if view == "week" else 4
        for day_key, slots in groups[:max_days]:
            day_date = datetime.fromisoformat(day_key).date()
            if day_date == now_local:
                day_label = "Сегодня"
            elif day_date == now_local + timedelta(days=1):
                day_label = "Завтра"
            else:
                day_label = day_date.strftime("%d.%m")
            row_buffer.append(
                InlineKeyboardButton(f"{day_label} ({len(slots)})", callback_data=f"cal:day:{day_key}")
            )
            if len(row_buffer) == max_columns:
                buttons.append(row_buffer)
                row_buffer = []
        if row_buffer:
            buttons.append(row_buffer)
        if overdue_count:
            buttons.append([InlineKeyboardButton(f"⚠️ Просрочено ({overdue_count})", callback_data="aq:all:all:0")])
        buttons.append(
            [
                InlineKeyboardButton("🕒 Время слотов", callback_data="sch:menu"),
                InlineKeyboardButton("⏱ Ритм генерации", callback_data="int:menu"),
            ]
        )
        buttons.append([InlineKeyboardButton("🔄 Обновить календарь", callback_data="cal:summary")])
        buttons.extend(self._submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
        return InlineKeyboardMarkup(buttons)

    def _calendar_day_rows(self, day_key: str) -> list[dict[str, Any]]:
        return self._scheduled_rows_for_day(day_key)

    def _calendar_day_slots(self, day_key: str) -> list[Any]:
        for group_key, slots in self._calendar_groups():
            if group_key == day_key:
                return list(slots)
        return []

    def _slots_for_day(self, day_value: date) -> list[tuple[int, int]]:
        tz = ZoneInfo(settings.tz_name)
        day_start = datetime.combine(day_value, time(hour=0, minute=0), tzinfo=tz)
        return [
            (slot.publish_at_local.hour, slot.publish_at_local.minute)
            for slot in build_schedule_window(day_start, days=1, control_rows=self._load_controls(), future_only=False)
        ]

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
        tz = ZoneInfo(settings.tz_name)
        slots = self._calendar_day_slots(day_key)
        if not slots and not rows:
            return f"Календарь публикаций\n\nНа {day_key} запланированных слотов нет."

        slot_map: dict[str, dict[str, Any]] = {}
        extra_rows: list[dict[str, Any]] = []
        for row in rows:
            publish_at = self._publish_at_utc(row)
            if publish_at is None:
                continue
            local_dt = publish_at.astimezone(tz)
            slot_map_key = local_dt.strftime("%H:%M")
            if slot_map_key in slot_map:
                extra_rows.append(row)
                continue
            slot_map[slot_map_key] = row

        lines = [f"Календарь: {day_key}", f"Занятых публикаций: {len(rows)}", ""]
        for index, slot in enumerate(slots, start=1):
            time_label = slot.publish_at_local.strftime("%H:%M")
            row = slot_map.get(time_label)
            kind_text = f"{publication_kind_badge(slot.publication_kind)} {publication_kind_label(slot.publication_kind)}"
            if row is None:
                lines.append(f"{index}. {time_label} {kind_text} — слот пока пуст")
                if slot.longread_topic:
                    lines.append(f"   Тема: {slot.longread_topic}")
                continue
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            format_label = _post_format_display_label(row)
            pillar = self._row_pillar(row)
            lines.append(f"{index}. {time_label} {kind_text} — {title[:76]}")
            lines.append(f"   Формат: {format_label} | Тема: {_pillar_label(pillar)}")
            if slot.longread_topic:
                lines.append(f"   Тема: {slot.longread_topic}")

        if extra_rows:
            lines.extend(["", "Вне базовой сетки:"])
            for row in extra_rows:
                publish_at = self._publish_at_utc(row)
                local_dt = publish_at.astimezone(tz) if publish_at else None
                time_label = local_dt.strftime("%H:%M") if local_dt else "--:--"
                title = str(row.get("title") or "Без заголовка").replace("\n", " ")
                kind = self._publication_kind(row)
                format_label = _post_format_display_label(row)
                pillar = self._row_pillar(row)
                lines.append(f"• {time_label} {publication_kind_badge(kind)} {title[:72]}")
                lines.append(f"  Формат: {format_label} | Тема: {_pillar_label(pillar)}")
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
            kind = self._publication_kind(row)
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{index}. {publication_kind_badge(kind)} {title[:40]}",
                        callback_data=f"cav:{row.get('id')}:{day_key}",
                    )
                ]
            )
        buttons.append(
            [
                InlineKeyboardButton("🕒 Время слотов", callback_data="sch:menu"),
                InlineKeyboardButton("🔄 Обновить день", callback_data=f"cal:day:{day_key}"),
                InlineKeyboardButton("🗓 Все дни", callback_data="cal:summary"),
            ]
        )
        buttons.extend(self._submenu_nav_rows(back_callback="cal:summary", back_label="🔙 К календарю"))
        return InlineKeyboardMarkup(buttons)

    def _schedule_settings_text(self) -> str:
        schedule = self._schedule_config(force_refresh=True)
        lines = [
            "Настройка автоматической сетки публикаций",
            "",
            f"• Будни утром: {'вкл' if schedule.daily_morning_enabled else 'выкл'} — {schedule_slot_label(schedule.daily_morning_slot)}",
            f"• Будни вечером: {'вкл' if schedule.daily_evening_enabled else 'выкл'} — {schedule_slot_label(schedule.daily_evening_slot)}",
            f"• Пятничный обзор: {'вкл' if schedule.weekly_review_enabled else 'выкл'} — {schedule_slot_label(schedule.weekly_review_slot)}",
            f"• Воскресный лонгрид: {'вкл' if schedule.longread_enabled else 'выкл'} — {schedule_slot_label(schedule.longread_slot)}",
            f"• Субботний юмор: {'вкл' if schedule.humor_enabled else 'выкл'} — {schedule_slot_label(schedule.humor_slot)}",
            "",
            "Лонгриды вращаются по тематическому пулу из 10 тем. Каждую позицию ниже можно открыть и перестроить без правки кода.",
        ]
        return "\n".join(lines)

    def _schedule_settings_keyboard(self) -> InlineKeyboardMarkup:
        section_buttons: list[InlineKeyboardButton] = []
        for alias in schedule_aliases():
            meta = schedule_alias_meta(alias)
            section_buttons.append(_inline_button(meta["label"], callback_data=f"sch:view:{alias}"))
        rows: list[list[InlineKeyboardButton]] = self._two_column_rows(section_buttons)
        rows.append(
            [
                _inline_button("📚 Темы лонгридов", callback_data="lt:menu"),
                _inline_button("⏱ Ритм генерации", callback_data="int:menu"),
            ]
        )
        rows.extend(self._submenu_nav_rows(back_callback="cal:summary", back_label="🔙 К календарю"))
        return InlineKeyboardMarkup(rows)

    def _schedule_detail_text(self, alias: str) -> str:
        schedule = self._schedule_config(force_refresh=True)
        meta = schedule_alias_meta(alias)
        slot_value = getattr(schedule, f"{alias}_slot")
        enabled = getattr(schedule, f"{alias}_enabled")
        options = getattr(schedule, f"{alias}_options")
        lines = [
            meta["label"],
            "",
            f"Тип публикации: {publication_kind_label(meta['kind'])}",
            f"Окно: {meta['window']}",
            f"Статус: {'включен' if enabled else 'выключен'}",
            f"Выбранное время: {schedule_slot_label(slot_value)}",
            "",
            "Доступные времена:",
            ", ".join(options),
        ]
        if alias == "longread":
            lines.extend(["", "Темы лонгридов:"])
            for index, topic in enumerate(schedule.longread_topics, start=1):
                lines.append(f"{index}. {topic}")
        return "\n".join(lines)

    def _schedule_detail_keyboard(self, alias: str) -> InlineKeyboardMarkup:
        schedule = self._schedule_config(force_refresh=True)
        enabled = getattr(schedule, f"{alias}_enabled")
        options = getattr(schedule, f"{alias}_options")
        rows: list[list[InlineKeyboardButton]] = [
            [
                _inline_button(
                    "☐ Выключить" if enabled else "✅ Включить",
                    callback_data=f"sch:toggle:{alias}",
                    style=_BUTTON_STYLE_SUCCESS if not enabled else None,
                )
            ]
        ]
        row_buffer: list[InlineKeyboardButton] = []
        for option in options:
            token = option.replace(":", "")
            row_buffer.append(_inline_button(option, callback_data=f"sch:set:{alias}:{token}"))
            if len(row_buffer) == 3:
                rows.append(row_buffer)
                row_buffer = []
        if row_buffer:
            rows.append(row_buffer)
        if alias == "longread":
            rows.append([_inline_button("📚 Темы лонгридов", callback_data="lt:menu")])
        rows.extend(self._submenu_nav_rows(back_callback="sch:menu", back_label="🔙 К сетке"))
        return InlineKeyboardMarkup(rows)

    def _longread_topics_text(self) -> str:
        active_topics = self._longread_topics_active(force_refresh=True)
        lines = [
            "Темы воскресных лонгридов",
            "",
            "Воскресный лонгрид выбирается автоматически из активного пула тем.",
            "Вы можете отключать или включать отдельные темы. Автовыбор будет вращаться только по активным позициям.",
            "",
            f"Активно тем: {len(active_topics)} из {len(_LONGREAD_TOPIC_LIBRARY)}",
            "",
        ]
        for index, topic in enumerate(_LONGREAD_TOPIC_LIBRARY, start=1):
            mark = "✅" if topic in active_topics else "☐"
            lines.append(f"{index}. {mark} {topic}")
        return "\n".join(lines)

    def _longread_topics_keyboard(self) -> InlineKeyboardMarkup:
        active_topics = set(self._longread_topics_active(force_refresh=True))
        topic_buttons: list[InlineKeyboardButton] = []
        for index, topic in enumerate(_LONGREAD_TOPIC_LIBRARY, start=1):
            label = f"{'✅' if topic in active_topics else '☐'} {index}. {topic[:34]}"
            topic_buttons.append(_inline_button(label, callback_data=f"lt:toggle:{index}"))
        rows: list[list[InlineKeyboardButton]] = self._two_column_rows(topic_buttons)
        rows.append([_inline_button("♻️ Сбросить к базовому пулу", callback_data="lt:reset")])
        rows.extend(self._submenu_nav_rows(back_callback="sch:menu", back_label="🔙 К сетке"))
        return InlineKeyboardMarkup(rows)

    def _interval_settings_text(self) -> str:
        generate_morning, generate_evening = self._configured_generate_times(force_refresh=True)
        telegram_morning, telegram_evening = self._configured_telegram_ingest_times(force_refresh=True)
        telegram_fetch_limit = self._configured_telegram_fetch_limit(force_refresh=True)
        publish_interval = self._configured_publish_interval(force_refresh=True)
        generate_limit = self._configured_generate_limit(force_refresh=True)
        retention_days = self._configured_review_retention_days(force_refresh=True)
        broad_ai_limit = self._configured_broad_ai_limit(force_refresh=True)
        return (
            "Ритм автоматической генерации и публикации\n\n"
            f"• Telegram-парсер: {telegram_morning} и {telegram_evening} (до {telegram_fetch_limit} сообщений/канал)\n"
            f"• Автогенерация: {generate_morning} и {generate_evening}\n"
            f"• Автопубликация: {_humanize_interval(publish_interval)}\n"
            f"• Лимит генерации за цикл: {generate_limit}\n\n"
            f"• Хранение драфтов На проверке: {retention_days} дн.\n\n"
            f"• Broad-AI в одном цикле: {broad_ai_limit}\n\n"
            "Генератор просыпается часто, но реально создает новые драфты только в указанные слоты."
        )

    def _interval_settings_keyboard(self) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = self._two_column_rows(
            [
                _inline_button("Парсер: утро", callback_data="int:view:telegram_morning"),
                _inline_button("Парсер: вечер", callback_data="int:view:telegram_evening"),
                _inline_button("Парсер: лимит", callback_data="int:view:telegram_limit"),
                _inline_button("Утренний слот", callback_data="int:view:generate_morning"),
                _inline_button("Вечерний слот", callback_data="int:view:generate_evening"),
                _inline_button("Публикация", callback_data="int:view:publish"),
                _inline_button("Лимит за цикл", callback_data="int:view:limit"),
                _inline_button("Хранение", callback_data="int:view:retention"),
                _inline_button("Broad-AI лимит", callback_data="int:view:broad_ai"),
            ]
        )
        rows.extend(self._submenu_nav_rows(back_callback="sch:menu", back_label="🔙 К сетке"))
        return InlineKeyboardMarkup(rows)

    def _interval_detail_text(self, kind: str) -> str:
        if kind == "generate_morning":
            current = self._configured_generate_times(force_refresh=True)[0]
            options = settings.news_generate_morning_options_list
            label = "Утренний слот автогенерации"
        elif kind == "generate_evening":
            current = self._configured_generate_times(force_refresh=True)[1]
            options = settings.news_generate_evening_options_list
            label = "Вечерний слот автогенерации"
        elif kind == "telegram_morning":
            current = self._configured_telegram_ingest_times(force_refresh=True)[0]
            options = settings.news_telegram_ingest_morning_options_list
            label = "Утренний слот Telegram-парсера"
        elif kind == "telegram_evening":
            current = self._configured_telegram_ingest_times(force_refresh=True)[1]
            options = settings.news_telegram_ingest_evening_options_list
            label = "Вечерний слот Telegram-парсера"
        elif kind == "telegram_limit":
            current = self._configured_telegram_fetch_limit(force_refresh=True)
            options = [30, 50, 80, 100, 150]
            label = "Лимит сообщений Telegram-парсера"
        elif kind == "publish":
            current = self._configured_publish_interval(force_refresh=True)
            options = settings.news_publish_interval_options_list
            label = "Автопубликация"
        elif kind == "retention":
            current = self._configured_review_retention_days(force_refresh=True)
            options = settings.news_review_retention_options_list
            label = "Хранение драфтов На проверке"
        elif kind == "broad_ai":
            current = self._configured_broad_ai_limit(force_refresh=True)
            options = self._configured_broad_ai_options(force_refresh=True)
            label = "Лимит broad-AI за цикл"
        else:
            current = self._configured_generate_limit(force_refresh=True)
            options = settings.news_generate_limit_options_list
            label = "Лимит генерации за цикл"

        options_line = ", ".join(
            _humanize_interval(item)
            if kind == "publish"
            else (f"{item} дн." if kind == "retention" else str(item))
            for item in options
        )
        current_label = _humanize_interval(current) if kind == "publish" else (f"{current} дн." if kind == "retention" else str(current))
        return (
            f"{label}\n\n"
            f"Текущее значение: {current_label}\n"
            f"Доступные варианты: {options_line}"
        )

    def _interval_detail_keyboard(self, kind: str) -> InlineKeyboardMarkup:
        if kind == "generate_morning":
            options = settings.news_generate_morning_options_list
        elif kind == "generate_evening":
            options = settings.news_generate_evening_options_list
        elif kind == "telegram_morning":
            options = settings.news_telegram_ingest_morning_options_list
        elif kind == "telegram_evening":
            options = settings.news_telegram_ingest_evening_options_list
        elif kind == "telegram_limit":
            options = [30, 50, 80, 100, 150]
        elif kind == "publish":
            options = settings.news_publish_interval_options_list
        elif kind == "retention":
            options = settings.news_review_retention_options_list
        elif kind == "broad_ai":
            options = self._configured_broad_ai_options(force_refresh=True)
        else:
            options = settings.news_generate_limit_options_list

        rows: list[list[InlineKeyboardButton]] = []
        row_buffer: list[InlineKeyboardButton] = []
        for option in options:
            if kind == "publish":
                label = _humanize_interval(option)
                value = str(option)
            elif kind == "retention":
                label = f"{option} дн."
                value = str(option)
            else:
                label = str(option)
                value = str(option).replace(":", "")
            row_buffer.append(_inline_button(label, callback_data=f"int:set:{kind}:{value}"))
            if len(row_buffer) == 3:
                rows.append(row_buffer)
                row_buffer = []
        if row_buffer:
            rows.append(row_buffer)
        rows.extend(self._submenu_nav_rows(back_callback="int:menu", back_label="🔙 К интервалам"))
        return InlineKeyboardMarkup(rows)

    def _day_publish_reason_keyboard(self, day_key: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=f"cpn:{day_key}"),
                    InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh"),
                ]
            ]
        )

    def _day_publish_confirm_keyboard(self, day_key: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Подтвердить публикацию дня", callback_data=f"cpc:{day_key}")],
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=f"cpn:{day_key}"),
                    InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh"),
                ],
            ]
        )

    def _get_post(self, post_id: str) -> dict[str, Any]:
        response = self.client.get_post(post_id)
        response.raise_for_status()
        return response.json()

    def _load_review_posts(
        self,
        review_filter: str,
        offset: int,
        kind_filter: str = "all",
        theme_filter: str = "all",
    ) -> tuple[int, list[dict[str, Any]]]:
        rows = self._list_posts_rows(status="review", newest_first=True, limit=100)
        if review_filter != "all":
            rows = [
                row
                for row in rows
                if _review_origin(str(row.get("format_type") or "")) == review_filter
            ]
        if kind_filter != "all":
            rows = [row for row in rows if self._publication_kind(row) == kind_filter]
        if theme_filter != "all":
            rows = [row for row in rows if self._row_pillar(row) == theme_filter]
        total = len(rows)
        return total, rows[offset : offset + _POSTS_PAGE_SIZE]

    def _posts_text(self, total: int, rows: list[dict[str, Any]], offset: int, status: str) -> str:
        label = _status_label(status)
        if not rows:
            return f"{label} (status={status})\n\nСейчас записей нет."

        lines = [f"{label}: {total}", ""]
        for idx, row in enumerate(rows, start=offset + 1):
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            publish_at = str(row.get("publish_at") or "")
            status_badge = _status_badge(str(row.get("status") or status))
            publication_kind = self._publication_kind(row)
            lines.append(f"{idx}. {status_badge} {publication_kind_badge(publication_kind)} {title[:86]}")
            lines.append(f"   ⏰ {publish_at} | {publication_kind_label(publication_kind)}")
        return "\n".join(lines)

    def _review_posts_text(
        self,
        total: int,
        rows: list[dict[str, Any]],
        offset: int,
        review_filter: str,
        kind_filter: str = "all",
        theme_filter: str = "all",
    ) -> str:
        label = _review_origin_label(review_filter)
        kind_label = "Все виды" if kind_filter == "all" else publication_kind_label(kind_filter)
        theme_label = "Все темы" if theme_filter == "all" else _pillar_display(theme_filter)
        if not rows:
            return (
                "🟡 На проверке\n\n"
                f"Фильтр: {label}\n"
                f"Вид: {kind_label}\n"
                f"Тема: {theme_label}\n\n"
                "Сейчас записей нет."
            )

        lines = [
            "🟡 На проверке",
            "",
            f"Фильтр: {label}",
            f"Вид: {kind_label}",
            f"Тема: {theme_label}",
            f"Всего: {total}",
            "",
        ]
        for idx, row in enumerate(rows, start=offset + 1):
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            publish_at = str(row.get("publish_at") or "")
            format_type = str(row.get("format_type") or "")
            origin_badge = _review_origin_badge(format_type)
            publication_kind = self._publication_kind(row)
            format_label = _post_format_display_label(row)
            pillar = self._row_pillar(row)
            lines.append(
                f"{idx}. {origin_badge} {publication_kind_badge(publication_kind)} {title[:80]}"
            )
            lines.append(f"   ⏰ {publish_at} | 🧭 {_pillar_label(pillar)} | {format_label}")
        return "\n".join(lines)

    def _manual_queue_text(
        self,
        total: int,
        rows: list[dict[str, Any]],
        offset: int,
        queue_filter: str,
        due_total: int,
        scheduled_total: int,
        theme_filter: str = "all",
    ) -> str:
        filter_label = "к публикации сейчас" if queue_filter == "due" else "все готовые"
        theme_label = "Все темы" if theme_filter == "all" else _pillar_display(theme_filter)
        if not rows:
            return (
                "Ручная очередь публикации (расширенный режим)\n\n"
                f"Фильтр: {filter_label}\n"
                f"Тема: {theme_label}\n"
                f"Готовые сейчас: {due_total} из {scheduled_total}\n\n"
                "Сейчас записей нет."
            )

        now_utc = datetime.now(timezone.utc)
        lines = [
            "Ручная очередь публикации (расширенный режим)",
            f"Фильтр: {filter_label}",
            f"Тема: {theme_label}",
            f"Готовые сейчас: {due_total} из {scheduled_total}",
            "Режимы топ-3/топ-5 доступны только в фильтре «К публикации сейчас».",
            "",
        ]
        for idx, row in enumerate(rows, start=offset + 1):
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            publish_at = str(row.get("publish_at") or "")
            publish_at_utc = self._publish_at_utc(row)
            due_mark = "⚡" if publish_at_utc and publish_at_utc <= now_utc else "🕒"
            publication_kind = self._publication_kind(row)
            pillar = self._row_pillar(row)
            format_label = _post_format_display_label(row)
            lines.append(f"{idx}. {due_mark} {publication_kind_badge(publication_kind)} {title[:84]}")
            lines.append(
                f"   ⏰ {publish_at} | {publication_kind_label(publication_kind)} | 🧭 {_pillar_label(pillar)} | {format_label}"
            )
        return "\n".join(lines)

    def _posts_keyboard(self, total: int, rows: list[dict[str, Any]], offset: int, status: str) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = []
        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            status_badge = _status_badge(str(row.get("status") or status))
            publication_kind = self._publication_kind(row)
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{idx}. {status_badge} {publication_kind_badge(publication_kind)} {title[:40]}",
                        callback_data=f"pv:{post_id}:{status}:{offset}",
                    )
                ]
            )

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
        buttons.extend(self._submenu_nav_rows(back_callback="sec:worklists", back_label="🔙 К рабочим спискам"))
        return InlineKeyboardMarkup(buttons)

    def _review_posts_keyboard(
        self,
        total: int,
        rows: list[dict[str, Any]],
        offset: int,
        review_filter: str,
        kind_filter: str = "all",
        theme_filter: str = "all",
    ) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = [
            [
                _inline_button(f"{'• ' if review_filter == 'all' else ''}Все", callback_data=f"rv:all:{kind_filter}:{theme_filter}:0"),
                _inline_button(f"{'• ' if review_filter == 'ai' else ''}AI", callback_data=f"rv:ai:{kind_filter}:{theme_filter}:0"),
                _inline_button(f"{'• ' if review_filter == 'manual' else ''}Ручные", callback_data=f"rv:manual:{kind_filter}:{theme_filter}:0"),
            ]
        ]
        kind_rows = [
            ("all", "Все виды"),
            ("daily", "Ежедневные"),
            ("weekly_review", "Обзоры"),
            ("longread", "Лонгриды"),
            ("humor", "Юмор"),
            ("other", "Прочее"),
        ]
        for index in range(0, len(kind_rows), 2):
            chunk = kind_rows[index : index + 2]
            buttons.append(
                [
                    _inline_button(
                        f"{'• ' if kind_filter == item_key else ''}{item_label}",
                        callback_data=f"rv:{review_filter}:{item_key}:{theme_filter}:0",
                    )
                    for item_key, item_label in chunk
                ]
            )
        theme_rows = [("all", "Все темы")] + [(pillar, _pillar_display(pillar)) for pillar in _PILLAR_LABELS]
        for index in range(0, len(theme_rows), 2):
            chunk = theme_rows[index : index + 2]
            buttons.append(
                [
                    _inline_button(
                        f"{'• ' if theme_filter == item_key else ''}{item_label}",
                        callback_data=f"rv:{review_filter}:{kind_filter}:{item_key}:0",
                    )
                    for item_key, item_label in chunk
                ]
            )
        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            origin_badge = _review_origin_badge(str(row.get("format_type") or ""))
            publication_kind = self._publication_kind(row)
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{idx}. {origin_badge} {publication_kind_badge(publication_kind)} {title[:38]}",
                        callback_data=f"pv:{post_id}:review:{offset}",
                    )
                ]
            )

        buttons.append([InlineKeyboardButton("✅ В готовые (все на странице)", callback_data="ba:ready:review:%d" % offset)])

        nav: list[InlineKeyboardButton] = []
        prev_offset = max(0, offset - _POSTS_PAGE_SIZE)
        next_offset = offset + _POSTS_PAGE_SIZE
        if offset > 0:
            nav.append(
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data=f"rv:{review_filter}:{kind_filter}:{theme_filter}:{prev_offset}",
                )
            )
        if next_offset < total:
            nav.append(
                InlineKeyboardButton(
                    "➡️ Далее",
                    callback_data=f"rv:{review_filter}:{kind_filter}:{theme_filter}:{next_offset}",
                )
            )
        if nav:
            buttons.append(nav)

        buttons.append(
            [
                InlineKeyboardButton(
                    "🔄 Обновить список",
                    callback_data=f"rv:{review_filter}:{kind_filter}:{theme_filter}:{offset}",
                )
            ]
        )
        buttons.extend(self._submenu_nav_rows(back_callback="sec:worklists", back_label="🔙 К рабочим спискам"))
        return InlineKeyboardMarkup(buttons)

    def _manual_queue_keyboard(
        self,
        total: int,
        rows: list[dict[str, Any]],
        offset: int,
        queue_filter: str,
        theme_filter: str = "all",
    ) -> InlineKeyboardMarkup:
        buttons: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton("⚡ К публикации сейчас", callback_data=f"mq:due:{theme_filter}:0"),
                InlineKeyboardButton("📚 Все готовые", callback_data=f"mq:all:{theme_filter}:0"),
            ]
        ]
        theme_rows = [("all", "Все темы")] + [(pillar, _pillar_display(pillar)) for pillar in _PILLAR_LABELS]
        for index in range(0, len(theme_rows), 2):
            chunk = theme_rows[index : index + 2]
            buttons.append(
                [
                    _inline_button(
                        f"{'• ' if theme_filter == item_key else ''}{item_label}",
                        callback_data=f"mq:{queue_filter}:{item_key}:0",
                    )
                    for item_key, item_label in chunk
                ]
            )
        context = _queue_context_from_filter(queue_filter, theme_filter)
        for idx, row in enumerate(rows, start=offset + 1):
            post_id = str(row.get("id"))
            title = str(row.get("title") or "Без заголовка").replace("\n", " ")
            publication_kind = self._publication_kind(row)
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{idx}. {publication_kind_badge(publication_kind)} {title[:40]}",
                        callback_data=f"pv:{post_id}:{context}:{offset}",
                    )
                ]
            )

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
            nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"mq:{queue_filter}:{theme_filter}:{prev_offset}"))
        if next_offset < total:
            nav.append(InlineKeyboardButton("➡️ Далее", callback_data=f"mq:{queue_filter}:{theme_filter}:{next_offset}"))
        if nav:
            buttons.append(nav)

        buttons.append([InlineKeyboardButton("🔄 Обновить очередь", callback_data=f"mq:{queue_filter}:{theme_filter}:{offset}")])
        buttons.extend(self._submenu_nav_rows(back_callback="sec:worklists", back_label="🔙 К рабочим спискам"))
        return InlineKeyboardMarkup(buttons)

    def _post_card_text(self, post: dict[str, Any]) -> str:
        title = str(post.get("title") or "Без заголовка")
        publish_at = str(post.get("publish_at") or "")
        status = str(post.get("status") or "")
        text = _strip_html_markup(str(post.get("text") or ""))
        format_type = str(post.get("format_type") or "n/a")
        format_label = _post_format_display_label(post)
        publication_kind = self._publication_kind(post)
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
            f"Вид публикации: {publication_kind_badge(publication_kind)} {publication_kind_label(publication_kind)}",
            f"Формат: {format_label}",
            f"Format type: {format_type}",
            f"CTA: {cta_type}",
            f"Тематика: {_pillar_display(pillar)}",
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
                    [InlineKeyboardButton("🧩 Добавить футер", callback_data=f"pf:{post_id}:{status}:{offset}")],
                    [InlineKeyboardButton("🗑 Нерелевантно / удалить", callback_data=f"pdd:{post_id}:{status}:{offset}", style=_BUTTON_STYLE_DANGER)],
                ]
            )
        else:
            rows.append([InlineKeyboardButton("🔄 Обновить карточку", callback_data=f"pv:{post_id}:{status}:{offset}")])
        if status == "draft":
            rows.append([InlineKeyboardButton("🟡 На проверку", callback_data=f"rr:{post_id}:{status}:{offset}")])
        if status in ("review", "failed"):
            rows.append([InlineKeyboardButton("✅ В готовые", callback_data=f"pr:{post_id}:{status}:{offset}")])
        if _is_auto_queue_context(status):
            queue_filter, theme_filter = _auto_queue_filters_from_context(status)
            rows.append([InlineKeyboardButton("🔙 К автоочереди", callback_data=f"aq:{queue_filter}:{theme_filter}:{offset}")])
        elif _is_calendar_context(status):
            rows.append([InlineKeyboardButton("🔙 К календарю", callback_data=f"cal:day:{_calendar_date_from_context(status)}")])
        elif _is_theme_context(status):
            rows.append([InlineKeyboardButton("🔙 К тематике", callback_data=f"th:{_theme_from_context(status)}:{offset}")])
        elif _is_source_context(status):
            rows.append([InlineKeyboardButton("🔙 К источнику", callback_data=f"src:{_source_from_context(status)}:{offset}")])
        elif _is_manual_queue_context(status):
            queue_filter, theme_filter = _queue_filters_from_context(status)
            rows.append([InlineKeyboardButton("🔙 К очереди", callback_data=f"mq:{queue_filter}:{theme_filter}:{offset}")])
        else:
            rows.append([InlineKeyboardButton("🔙 К списку", callback_data=f"pl:{status}:{offset}")])
        rows.append([InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh")])
        return InlineKeyboardMarkup(rows)

    def _publish_confirm_keyboard(self, post_id: str, status: str, offset: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Подтвердить публикацию", callback_data=f"ppy:{post_id}:{status}:{offset}")],
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=f"ppn:{post_id}:{status}:{offset}"),
                    InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh"),
                ],
            ]
        )

    def _publish_reason_keyboard(self, post_id: str, status: str, offset: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=f"ppn:{post_id}:{status}:{offset}"),
                    InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh"),
                ]
            ]
        )

    def _delete_reason_keyboard(self, post_id: str, status: str, offset: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=f"pdn:{post_id}:{status}:{offset}"),
                    InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh"),
                ]
            ]
        )

    def _delete_confirm_keyboard(self, post_id: str, status: str, offset: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🗑 Удалить пост", callback_data=f"pdy:{post_id}:{status}:{offset}")],
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=f"pdn:{post_id}:{status}:{offset}"),
                    InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh"),
                ],
            ]
        )

    def _batch_publish_reason_keyboard(self, queue_filter: str, offset: int, mode: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=f"mbn:{queue_filter}:{offset}:{mode}"),
                    InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh"),
                ]
            ]
        )

    def _batch_publish_confirm_keyboard(self, queue_filter: str, offset: int, mode: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Подтвердить пакетную публикацию", callback_data=f"mbc:{queue_filter}:{offset}:{mode}")],
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=f"mbn:{queue_filter}:{offset}:{mode}"),
                    InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh"),
                ],
            ]
        )

    def _create_start_keyboard(self) -> InlineKeyboardMarkup:
        rows = self._two_column_rows(
            [
                InlineKeyboardButton("✍️ Написать вручную", callback_data="cn:manual"),
                InlineKeyboardButton("🤖 По тезисам", callback_data="cn:ai"),
                InlineKeyboardButton("🎙 Из транскриба / voice", callback_data="cn:transcript"),
            ]
        )
        rows.extend(self._submenu_nav_rows(back_callback="cn:cancel"))
        return InlineKeyboardMarkup(rows)

    def _create_kind_keyboard(self) -> InlineKeyboardMarkup:
        rows = self._two_column_rows(
            [InlineKeyboardButton(_manual_post_kind_label(kind), callback_data=f"ck:{kind}") for kind in _MANUAL_POST_TYPE_ORDER]
        )
        rows.extend(self._submenu_nav_rows(back_callback="cn:cancel"))
        return InlineKeyboardMarkup(rows)

    def _create_theme_keyboard(self) -> InlineKeyboardMarkup:
        rows = self._two_column_rows(
            [InlineKeyboardButton(_manual_theme_label(theme), callback_data=f"ct:{theme}") for theme in _MANUAL_THEME_ORDER]
        )
        rows.extend(self._submenu_nav_rows(back_callback="cn:cancel"))
        return InlineKeyboardMarkup(rows)

    def _create_media_keyboard(
        self,
        *,
        can_clear: bool = False,
        media_count: int = 0,
        editing: bool = False,
    ) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        if media_count > 0:
            rows.append([InlineKeyboardButton(f"✅ Готово ({media_count})", callback_data="cm:done")])
        elif not editing:
            rows.append([InlineKeyboardButton("⏭ Без медиа", callback_data="cm:skip")])
        else:
            rows.append([InlineKeyboardButton("✅ Готово", callback_data="cm:done")])
        if can_clear:
            rows.insert(0, [InlineKeyboardButton("🗑 Убрать медиа", callback_data="cm:clear")])
        rows.append(
            [
                InlineKeyboardButton("🔙 Назад", callback_data="cn:cancel"),
                InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh"),
            ]
        )
        return InlineKeyboardMarkup(rows)

    def _create_link_keyboard(self, *, can_clear: bool = False, cancel_callback: str = "cn:cancel") -> InlineKeyboardMarkup:
        rows = [[InlineKeyboardButton("⏭ Без ссылки", callback_data="cl:skip")]]
        if can_clear:
            rows.insert(0, [InlineKeyboardButton("🗑 Убрать ссылку", callback_data="cl:clear")])
        rows.append(
            [
                InlineKeyboardButton("🔙 Назад", callback_data=cancel_callback),
                InlineKeyboardButton("🏠 Рабочий стол", callback_data="refresh"),
            ]
        )
        return InlineKeyboardMarkup(rows)

    def _create_draft_keyboard(self) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton("🧱 Тип", callback_data="ce:kind"),
                InlineKeyboardButton("🧭 Тема", callback_data="ce:theme"),
            ],
            [
                InlineKeyboardButton("🖼 Медиа", callback_data="ce:media"),
                InlineKeyboardButton("🔗 Ссылка", callback_data="ce:link"),
            ],
            [
                InlineKeyboardButton("🗂 Материал", callback_data="ce:source"),
                InlineKeyboardButton("✏️ Заголовок", callback_data="ce:title"),
            ],
            [InlineKeyboardButton("📝 Текст", callback_data="ce:text")],
            [InlineKeyboardButton("🤖 Доработать через LLM", callback_data="ce:ai")],
            [InlineKeyboardButton("🆕 Сохранить в черновики", callback_data="cs:draft")],
            [InlineKeyboardButton("🟡 Отправить на проверку", callback_data="cs:review")],
            [
                InlineKeyboardButton("✅ +1ч", callback_data="cs:scheduled:h1"),
                InlineKeyboardButton("🌙 19:00", callback_data="cs:scheduled:e19"),
            ],
            [InlineKeyboardButton("🌤 Завтра 10:00", callback_data="cs:scheduled:t10")],
        ]
        rows.append(
            [
                InlineKeyboardButton("⤴️ Последнее в начало", callback_data="cr:lastfirst"),
                InlineKeyboardButton("🔄 Развернуть медиа", callback_data="cr:reverse"),
            ]
        )
        rows.append([InlineKeyboardButton("🧹 Новый с нуля", callback_data="cn:start")])
        rows.extend(self._submenu_nav_rows(back_callback="cn:start"))
        return InlineKeyboardMarkup(rows)

    async def _show_create_start(self, update: Update) -> None:
        post_types = "\n".join(
            f"• {_manual_post_kind_label(kind)} — {_manual_post_kind_structure(kind)}"
            for kind in _MANUAL_POST_TYPE_ORDER
        )
        context_text = (
            "Создание нового поста\n\n"
            "Контур ручного редактора:\n"
            "1. Выбираете режим, тип поста и тематику\n"
            "2. Добавляете медиа и, если нужно, ссылку на источник\n"
            "3. Присылаете материал: текст, тезисы или Telegram-транскриб\n"
            "4. Получаете драфт, правите и отправляете в очередь\n\n"
            "Режимы:\n"
            "✍️ вручную — вы задаете основной текст сами\n"
            "🤖 через LLM — вы даете материал, бот собирает черновик\n\n"
            "🎙 из транскриба / voice — вы даете текстовую расшифровку голосового или устного материала, "
            "бот мягко очищает устную речь и собирает драфт\n\n"
            f"Доступные типы:\n{post_types}\n\n"
            "Сильные опорные типы:\n"
            f"{_manual_post_kind_label('promo_offer')}\n{_manual_post_kind_screen_template('promo_offer')}\n\n"
            f"{_manual_post_kind_label('opinion')}\n{_manual_post_kind_screen_template('opinion')}\n\n"
            f"{_manual_post_kind_label('case_story')}\n{_manual_post_kind_screen_template('case_story')}\n\n"
            "Далее сможете сохранить материал в черновики, на проверку или сразу в автоплан публикации."
        )
        await update.effective_message.reply_text(context_text, reply_markup=self._create_start_keyboard())

    async def _show_create_draft(self, message, draft: dict[str, Any]) -> None:
        await message.reply_text(
            self._render_create_preview(draft),
            reply_markup=self._create_draft_keyboard(),
        )

    def _render_create_preview(self, draft: dict[str, Any]) -> str:
        title = str(draft.get("title") or "Без заголовка")
        text = _strip_html_markup(self._compose_create_text(draft))
        preview = text if len(text) <= 2500 else text[:2500] + "\n\n…"
        mode = str(draft.get("mode") or "manual")
        mode_label = "LLM" if mode == "ai" else "ручной"
        kind = str(draft.get("kind") or "")
        theme = str(draft.get("theme") or "")
        source_material = str(draft.get("source_material") or "").strip()
        source_url = str(draft.get("source_url") or "").strip()
        media_urls = draft.get("media_urls") or []
        footer = build_manual_footer(kind)
        media_block = (
            "Порядок медиа:\n" + "\n".join(_media_preview_label(item, index) for index, item in enumerate(media_urls, start=1)) + "\n"
            if media_urls
            else ""
        )
        return "".join(
            [
                "Черновик нового поста\n\n",
                f"Заголовок: {title}\n",
                f"Тип: {_manual_post_kind_label(kind)}\n",
                f"Тема: {_manual_theme_label(theme)}\n",
                f"Режим: {mode_label}\n",
                f"Шаблон: {_manual_post_kind_structure(kind)}\n",
                f"Опорный шаблон:\n{_manual_post_kind_screen_template(kind)}\n",
                f"Медиа: {'да' if media_urls else 'нет'}\n",
                media_block,
                f"Ссылка: {source_url[:180]}\n" if source_url else "Ссылка: нет\n",
                f"Длина итогового текста: {len(text)} символов\n",
                f"Материал: {source_material[:220]}\n" if source_material else "",
                f"Фокус темы: {_manual_theme_note(theme)}\n" if theme else "",
                f"Футер: {_manual_footer_mode_label(kind)}\n",
                f"Текст футера: {footer[:180]}\n" if footer else "",
                "\n",
                f"{preview}\n\n",
                "Можно доработать черновик или сразу сохранить:",
            ]
        )

    def _compose_create_text(self, draft: dict[str, Any]) -> str:
        return compose_manual_post_html(
            str(draft.get("title") or ""),
            str(draft.get("text") or ""),
            str(draft.get("kind") or ""),
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
            "text": self._compose_create_text(draft),
            "media_urls": list(draft.get("media_urls") or []) or None,
            "source_url": str(draft.get("source_url") or "").strip() or f"manual://{str(draft.get('theme') or 'manual')}/{str(draft.get('kind') or 'post')}",
            "publish_at": publish_at.isoformat(),
            "status": status,
            "format_type": f"{'manual' if str(draft.get('mode') or 'manual') == 'manual' else 'operator_ai'}_{str(draft.get('kind') or 'generic')}",
            "cta_type": str(draft.get("kind") or "manual"),
            "rubric": _manual_theme_rubric(str(draft.get("theme") or "")) or _manual_post_kind_rubric(str(draft.get("kind") or "")),
        }

    @staticmethod
    def _generation_preview_payload(preview: dict[str, Any]) -> dict[str, Any]:
        return {
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

    def _save_generation_previews_to_review(
        self,
        previews: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int, int]:
        created_posts: list[dict[str, Any]] = []
        duplicates = 0
        failed = 0
        for preview in previews:
            response = self.client.create_scheduled_post(self._generation_preview_payload(preview))
            if response.status_code in (200, 201):
                created_posts.append(response.json())
                continue
            if response.status_code == 409:
                duplicates += 1
                continue
            failed += 1
            logger.error(
                "generation_preview_save_failed",
                extra={"status": response.status_code, "body": response.text[:500]},
            )
        if created_posts or duplicates or failed:
            self._invalidate_post_caches()
        return created_posts, duplicates, failed

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
            caption = (text or "")[:1020]
            remainder = (text or "")[1020:].strip()

            def _resolve_media_item(media: str) -> tuple[str, str]:
                if media.startswith("tgphoto://"):
                    return "photo", media.replace("tgphoto://", "", 1)
                if media.startswith("tgvideo://"):
                    return "video", media.replace("tgvideo://", "", 1)
                if media.startswith("tgdocument://"):
                    return "document", media.replace("tgdocument://", "", 1)
                return "photo", media.replace("tg://", "", 1) if media.startswith("tg://") else media

            resolved = [_resolve_media_item(item) for item in media_urls if item]
            album_eligible = len(resolved) > 1 and all(kind in {"photo", "video"} for kind, _ in resolved)

            if album_eligible:
                media_group: list[Any] = []
                for index, (kind, payload) in enumerate(resolved[:10]):
                    kwargs: dict[str, Any] = {}
                    if index == 0 and caption:
                        kwargs["caption"] = caption
                        kwargs["parse_mode"] = "HTML"
                    if kind == "photo":
                        media_group.append(InputMediaPhoto(media=payload, **kwargs))
                    else:
                        media_group.append(InputMediaVideo(media=payload, **kwargs))
                messages = await context.bot.send_media_group(chat_id=chat_id, media=media_group)
                message = messages[0]
            else:
                message = None
                for index, (kind, payload) in enumerate(resolved):
                    kwargs: dict[str, Any] = {}
                    if index == 0 and caption:
                        kwargs["caption"] = caption
                        kwargs["parse_mode"] = "HTML"
                    if kind == "photo":
                        sent = await context.bot.send_photo(chat_id=chat_id, photo=payload, **kwargs)
                    elif kind == "video":
                        sent = await context.bot.send_video(chat_id=chat_id, video=payload, **kwargs)
                    else:
                        sent = await context.bot.send_document(chat_id=chat_id, document=payload, **kwargs)
                    if message is None:
                        message = sent
                if message is None:
                    raise RuntimeError("Не удалось отправить медиа")

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

    def _fallback_footer_text(self, post: dict[str, Any]) -> str:
        format_type = str(post.get("format_type") or "")
        manual_kind = _manual_post_kind_from_format_type(format_type)
        if manual_kind != "service_page":
            footer = build_manual_footer(manual_kind)
            if footer:
                return footer

        title = str(post.get("title") or "")
        text = _strip_html_markup(str(post.get("text") or ""))
        rubric = str(post.get("rubric") or "")
        pillar = normalize_rubric_to_pillar(rubric, f"{title}\n{text}")
        variant_index = self._footer_variant_index(post)
        options_by_pillar = {
            "tools": (
                "Если у вас похожая задача, можем помочь подобрать и безопасно встроить такой AI-инструмент в юридические процессы. Написать можно в @legal_ai_helper_new_bot.",
                "Такие решения уже можно примерять на работу юротдела без лишних рисков по данным и лицензиям. Если хотите разобрать ваш кейс, напишите в @legal_ai_helper_new_bot.",
                "Из таких инструментов обычно вырастают рабочие сценарии автоматизации для юрфункции. Если хотите понять, где это даст эффект у вас, напишите в @legal_ai_helper_new_bot.",
            ),
            "implementation": (
                "Если думаете, как внедрить похожую автоматизацию в заявки, договорную работу или внутренние процессы, напишите в @legal_ai_helper_new_bot.",
                "На практике такие сценарии хорошо ложатся на типовые юридические процессы. Если хотите разобрать ваш контур внедрения, напишите в @legal_ai_helper_new_bot.",
                "Если для вашей команды это тоже актуально, можем помочь превратить такой кейс в понятный план внедрения. Написать можно в @legal_ai_helper_new_bot.",
            ),
            "case": (
                "Если хотите примерить похожий сценарий автоматизации на вашу юридическую функцию, напишите в @legal_ai_helper_new_bot.",
                "Из таких кейсов обычно вырастают пилоты по автоматизации юрпроцессов. Если хотите обсудить ваш процесс, напишите в @legal_ai_helper_new_bot.",
                "Если у вас похожая операционная боль, можем помочь собрать рабочий сценарий внедрения. Написать можно в @legal_ai_helper_new_bot.",
            ),
            "regulation": (
                "Если хотите внедрять похожие AI-сценарии с учетом privacy, compliance и регуляторных ограничений, напишите в @legal_ai_helper_new_bot.",
                "Такие сигналы важны не только сами по себе, но и для практики внедрения AI в юрфункции. Если хотите разобрать ваш контур, напишите в @legal_ai_helper_new_bot.",
                "Если для вас актуален вопрос, как внедрять подобные решения без конфликтов с регулированием, напишите в @legal_ai_helper_new_bot.",
            ),
            "market": (
                "Если хотите перевести такой рыночный сигнал в реальный план автоматизации для юрфункции или Legal AI-продукта, напишите в @legal_ai_helper_new_bot.",
                "Из таких движений рынка обычно рождаются прикладные проекты для юркоманд. Если хотите обсудить ваш сценарий, напишите в @legal_ai_helper_new_bot.",
                "Если думаете, как превратить этот тренд в полезное внедрение для вашей юридической функции, напишите в @legal_ai_helper_new_bot.",
            ),
        }
        options = options_by_pillar.get(
            pillar,
            (
                "Если хотите понять, как внедрить похожую автоматизацию в вашей юридической функции, напишите в @legal_ai_helper_new_bot.",
                "Если для вашей команды эта тема тоже прикладная, можем помочь разобрать сценарий внедрения. Написать можно в @legal_ai_helper_new_bot.",
                "Такие кейсы уже можно превращать в рабочие AI-сценарии для юрфункции. Если хотите обсудить ваш процесс, напишите в @legal_ai_helper_new_bot.",
            ),
        )
        return options[variant_index % len(options)]

    @staticmethod
    def _footer_variant_index(post: dict[str, Any]) -> int:
        seed = "|".join(
            [
                str(post.get("id") or ""),
                str(post.get("title") or ""),
                str(post.get("rubric") or ""),
                str(post.get("format_type") or ""),
            ]
        ).encode("utf-8")
        digest = hashlib.sha256(seed).digest()
        return digest[0] % len(_FOOTER_VARIANT_HINTS)

    def _generate_footer_with_llm(self, post: dict[str, Any]) -> str:
        client = self._get_openai_client()
        title = str(post.get("title") or "Без заголовка").strip()
        text = _strip_html_markup(str(post.get("text") or "")).strip()
        format_type = str(post.get("format_type") or "standard").strip()
        cta_type = str(post.get("cta_type") or "soft").strip()
        rubric = str(post.get("rubric") or "").strip()
        pillar = normalize_rubric_to_pillar(rubric, f"{title}\n{text}")
        variant_hint = _FOOTER_VARIANT_HINTS[self._footer_variant_index(post)]

        if self._use_max_tokens_param:
            completion_kwargs: dict[str, Any] = {"max_tokens": 220}
        else:
            completion_kwargs = {"max_completion_tokens": 220}

        response = client.chat.completions.create(
            model=settings.news_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты редактор Telegram-канала Legal AI PRO. "
                        "Сформируй только footer для уже готового поста. "
                        "Footer должен быть коротким, деловым, ненавязчивым и логично продолжать именно этот материал. "
                        "Смысл footer: показать, что мы можем помочь внедрить похожую автоматизацию или AI-сценарий в юридической функции клиента. "
                        "Footer должен мягко подводить к заявке на автоматизацию, а не звучать как реклама ради рекламы. "
                        "Обязательно веди в лид-бот @legal_ai_helper_new_bot. "
                        "Если пост про инструменты, внедрение, legal ops или практический кейс, предложи спокойный следующий шаг по внедрению. "
                        "Если пост нейтральный или регуляторный, footer должен оставаться мягким, но все равно связывать тему с практикой внедрения и возможностью написать в бота. "
                        "Избегай однообразного старта каждого footer. Не повторяй из поста в пост одну и ту же формулу. "
                        "Не начинай каждый раз с 'Если хотите'. Разнообразь заход, сохраняя деловой тон. "
                        "Верни только текст footer на 1-2 предложения, без заголовка 'Следующий шаг', без markdown и без JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Заголовок: {title}\n"
                        f"Формат: {format_type}\n"
                        f"CTA-режим: {cta_type}\n"
                        f"Рубрика: {rubric or '—'}\n"
                        f"Тематика: {_pillar_label(pillar)}\n\n"
                        f"Пожелание по формулировке: {variant_hint}\n\n"
                        f"Текст поста:\n{text}\n\n"
                        "Сформируй только footer. "
                        "Он должен логично вытекать из смысла поста и аккуратно предлагать написать в @legal_ai_helper_new_bot, "
                        "если читатель хочет внедрить похожую автоматизацию или AI-сценарий."
                    ),
                },
            ],
            temperature=0.55,
            **completion_kwargs,
        )
        content = (response.choices[0].message.content or "").strip()
        content = re.sub(r"^\s*(?:следующий шаг|footer)\s*:?\s*", "", content, flags=re.IGNORECASE).strip()
        content = re.sub(r"\s+", " ", content).strip()
        return content or self._fallback_footer_text(post)

    @staticmethod
    def _apply_footer_to_post_text(original_text: str, footer_text: str) -> str:
        text = (original_text or "").strip()
        text = _FOOTER_BLOCK_RE.sub("", text).strip()
        footer_text = re.sub(r"\s+", " ", (footer_text or "").strip())
        if not footer_text:
            return normalize_post_text(text)

        footer_block = f"<b>Следующий шаг</b>\n{html.escape(footer_text)}"
        source_index = text.find("<b>Источник</b>")
        if source_index != -1:
            updated = f"{text[:source_index].rstrip()}\n\n{footer_block}\n\n{text[source_index:].lstrip()}"
        else:
            updated = f"{text.rstrip()}\n\n{footer_block}"
        return normalize_post_text(updated)

    def _draft_post_with_llm(self, title: str, source_material: str, post_kind: str, *, source_mode: str = "ai", theme: str = "") -> str:
        client = self._get_openai_client()
        system_prompt = (
            "Ты редактор Telegram-канала Legal AI PRO. "
            "Собери профессиональный, плотный по смыслу пост на русском языке. "
            "Тон: деловой, уверенный, без воды и кликбейта. "
            "Не выдумывай факты, которых нет в тезисах пользователя. "
            "Не добавляй в конце CTA и не дублируй заголовок. "
            "Верни только основной текст поста без JSON и без markdown-блоков."
        )
        completion_kwargs: dict[str, Any]
        if self._use_max_tokens_param:
            completion_kwargs = {"max_tokens": 1500}
        else:
            completion_kwargs = {"max_completion_tokens": 1500}

        prepared_source = _normalize_transcript_text(source_material) if source_mode == "transcript" else source_material
        transcript_hint = (
            "Источник — расшифровка устной речи. Сначала тихо очисти паразиты устной речи, повторы, оговорки и шум, "
            "но не меняй фактический смысл. Затем собери читабельный Telegram-пост."
            if source_mode == "transcript"
            else "Источник — тезисы, заметки или текстовый материал. Собери из него плотный Telegram-пост."
        )

        response = client.chat.completions.create(
            model=settings.news_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Заголовок: {title}\n\n"
                        f"Тип поста: {_manual_post_kind_label(post_kind)}\n"
                        f"Профиль типа: {_manual_post_kind_note(post_kind)}\n"
                        f"Тема: {_manual_theme_label(theme)}\n"
                        f"Фокус темы: {_manual_theme_note(theme)}\n"
                        f"Шаблон: {_manual_post_kind_structure(post_kind)}\n"
                        f"Инструкция по типу: {_manual_post_kind_llm_hint(post_kind)}\n\n"
                        f"Стилистика типа: {_manual_post_kind_style_hint(post_kind)}\n\n"
                        f"{_manual_post_kind_prompt_block(post_kind)}\n\n"
                        f"Режим источника: {source_mode}\n"
                        f"Инструкция по очистке источника: {transcript_hint}\n\n"
                        f"Материал / тезисы / транскриб:\n{prepared_source}\n\n"
                        "Собери основной текст Telegram-поста для канала об AI и автоматизации юридической функции."
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
        counts, _ = await self._queue_snapshot()
        if intro:
            text = (
                "Рабочий стол контент-бота Legal AI PRO\n\n"
                "Это единый вход в редакторский контур: автопилот, очереди постов, календарь, источники, тематики и ручное создание постов.\n\n"
                + text
            )
        try:
            removal_message = await update.effective_message.reply_text(
                "…",
                reply_markup=_main_menu_markup(),
            )
            try:
                await removal_message.delete()
            except Exception:
                pass
        except Exception:
            pass
        await update.effective_message.reply_text(
            text,
            reply_markup=self._workspace_keyboard(counts),
        )

    async def _show_sections_message(self, update: Update) -> None:
        await self._show_panel_message(update, intro=False)

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
        generation_counts = self._generation_theme_stats()
        await update.effective_message.reply_text(
            self._themes_text(counts, generation_counts),
            reply_markup=self._themes_keyboard(counts, generation_counts),
        )

    async def _show_generation_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        controls = self._controls_map(force_refresh=True)
        await update.effective_message.reply_text(
            self._generation_text(controls),
            reply_markup=self._generation_keyboard(),
        )

    async def _show_auto_queue(self, update: Update, queue_filter: str = "all", offset: int = 0, theme_filter: str = "all") -> None:
        total, rows, overdue = self._load_auto_queue(queue_filter=queue_filter, offset=offset, theme_filter=theme_filter)
        await update.effective_message.reply_text(
            self._auto_queue_text(total, rows, offset, overdue, queue_filter, theme_filter),
            reply_markup=self._auto_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
        )

    async def _show_posts_status(self, update: Update, status: str, offset: int = 0) -> None:
        total, rows = self._load_posts(status=status, offset=offset)
        await update.effective_message.reply_text(
            self._posts_text(total, rows, offset, status),
            reply_markup=self._posts_keyboard(total, rows, offset, status),
        )

    async def _show_manual_queue(self, update: Update, queue_filter: str = "due", offset: int = 0, theme_filter: str = "all") -> None:
        total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset, theme_filter=theme_filter)
        await update.effective_message.reply_text(
            self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total, theme_filter),
            reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
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
                BotCommand("start", "Открыть рабочий стол"),
                BotCommand("admin", "Рабочий стол"),
                BotCommand("newpost", "Создать пост"),
                BotCommand("calendar", "Календарь публикаций"),
                BotCommand("generate_now", "Принудительная генерация"),
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
            await update.effective_message.reply_text(f"Ошибка загрузки рабочего стола: {exc}", reply_markup=_main_menu_markup())

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            await self._show_panel_message(update, intro=True)
        except Exception as exc:
            logger.exception("admin_start_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(f"Ошибка запуска рабочего стола: {exc}", reply_markup=_main_menu_markup())

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

    async def cmd_autoqueue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if not await self._ensure_admin(update):
            return
        try:
            await self._show_auto_queue(update, queue_filter="all", offset=0)
        except Exception as exc:
            logger.exception("auto_queue_load_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(
                f"Ошибка загрузки автоочереди: {exc}",
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
            logger.exception("workspace_load_failed", extra={"error": str(exc)})
            await update.effective_message.reply_text(
                f"Ошибка загрузки рабочего стола: {exc}",
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
            payload = response.json()
            await update.effective_message.reply_text(
                _worker_list_text(payload),
                reply_markup=self._workers_keyboard(payload),
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
            self._help_text(),
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
                    reply_markup=self._calendar_summary_keyboard(groups, view="week"),
                )
                return

            if data == "cal:view:month":
                groups = self._calendar_groups()
                await self._safe_edit_message_text(
                    query,
                    self._calendar_month_text(groups),
                    reply_markup=self._calendar_summary_keyboard(groups, view="month"),
                )
                return

            if data.startswith("cal:view:day:"):
                day_key = data.split(":", maxsplit=3)[3]
                rows = self._calendar_day_rows(day_key)
                await self._safe_edit_message_text(
                    query,
                    self._calendar_day_text(day_key, rows),
                    reply_markup=self._calendar_day_keyboard(day_key, rows),
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
                context.user_data[_STATE_PENDING_CREATE] = {"mode": "manual", "step": "kind"}
                context.user_data.pop(_STATE_DRAFT_CREATE, None)
                await self._safe_edit_message_text(
                    query,
                    "Новый пост: шаг 1 из 5\n\n"
                    "Выберите тип материала.",
                    reply_markup=self._create_kind_keyboard(),
                )
                return

            if data == "cn:ai":
                context.user_data[_STATE_PENDING_CREATE] = {"mode": "ai", "step": "kind"}
                context.user_data.pop(_STATE_DRAFT_CREATE, None)
                await self._safe_edit_message_text(
                    query,
                    "Новый пост через LLM: шаг 1 из 5\n\n"
                    "Выберите тип материала.",
                    reply_markup=self._create_kind_keyboard(),
                )
                return

            if data == "cn:transcript":
                context.user_data[_STATE_PENDING_CREATE] = {"mode": "transcript", "step": "kind"}
                context.user_data.pop(_STATE_DRAFT_CREATE, None)
                await self._safe_edit_message_text(
                    query,
                    "Новый пост из транскриба: шаг 1 из 5\n\n"
                    "Выберите тип материала.",
                    reply_markup=self._create_kind_keyboard(),
                )
                return

            if data.startswith("ck:"):
                _, kind = data.split(":", maxsplit=1)
                pending = dict(context.user_data.get(_STATE_PENDING_CREATE) or {})
                if not pending:
                    pending = {"mode": "manual", "step": "kind"}
                draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
                step = str(pending.get("step") or "")
                if step == "edit_kind" and draft:
                    draft["kind"] = kind
                    context.user_data[_STATE_DRAFT_CREATE] = draft
                    context.user_data.pop(_STATE_PENDING_CREATE, None)
                    await self._safe_edit_message_text(
                        query,
                        self._render_create_preview(draft),
                        reply_markup=self._create_draft_keyboard(),
                    )
                    return
                pending["kind"] = kind
                pending["step"] = "theme"
                context.user_data[_STATE_PENDING_CREATE] = pending
                await self._safe_edit_message_text(
                    query,
                    "Новый пост: шаг 2 из 5\n\n"
                    f"Тип: {_manual_post_kind_label(kind)}\n"
                    f"{_manual_post_kind_note(kind)}\n"
                    f"{_manual_post_kind_structure(kind)}\n\n"
                    f"{_manual_post_kind_screen_template(kind)}\n\n"
                    "Выберите тематику поста.",
                    reply_markup=self._create_theme_keyboard(),
                )
                return

            if data.startswith("ct:"):
                _, theme = data.split(":", maxsplit=1)
                pending = dict(context.user_data.get(_STATE_PENDING_CREATE) or {})
                draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
                step = str(pending.get("step") or "")
                if step == "edit_theme" and draft:
                    draft["theme"] = theme
                    context.user_data[_STATE_DRAFT_CREATE] = draft
                    context.user_data.pop(_STATE_PENDING_CREATE, None)
                    await self._safe_edit_message_text(
                        query,
                        self._render_create_preview(draft),
                        reply_markup=self._create_draft_keyboard(),
                    )
                    return
                pending["theme"] = theme
                pending["step"] = "media"
                context.user_data[_STATE_PENDING_CREATE] = pending
                await self._safe_edit_message_text(
                    query,
                    "Новый пост: шаг 3 из 5\n\n"
                    f"Тип: {_manual_post_kind_label(str(pending.get('kind') or ''))}\n"
                    f"Тема: {_manual_theme_label(theme)}\n"
                    f"{_manual_theme_note(theme)}\n\n"
                    f"{_manual_post_kind_screen_template(str(pending.get('kind') or ''))}\n\n"
                    "Пришлите изображение/видео для поста или нажмите «Без медиа».",
                    reply_markup=self._create_media_keyboard(),
                )
                return

            if data == "cm:skip":
                pending = dict(context.user_data.get(_STATE_PENDING_CREATE) or {})
                draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
                step = str(pending.get("step") or "")
                if step == "edit_media" and draft:
                    context.user_data.pop(_STATE_PENDING_CREATE, None)
                    await self._safe_edit_message_text(
                        query,
                        self._render_create_preview(draft),
                        reply_markup=self._create_draft_keyboard(),
                    )
                    return
                pending["step"] = "source_link"
                context.user_data[_STATE_PENDING_CREATE] = pending
                await self._safe_edit_message_text(
                    query,
                    "Новый пост: шаг 4 из 5\n\n"
                    "Если есть статья, пост или материал-источник, пришлите ссылку одним сообщением.\n"
                    "Если ссылки нет, нажмите «Без ссылки».",
                    reply_markup=self._create_link_keyboard(),
                )
                return

            if data == "cm:done":
                pending = dict(context.user_data.get(_STATE_PENDING_CREATE) or {})
                draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
                step = str(pending.get("step") or "")
                if step == "edit_media" and draft:
                    context.user_data.pop(_STATE_PENDING_CREATE, None)
                    await self._safe_edit_message_text(
                        query,
                        self._render_create_preview(draft),
                        reply_markup=self._create_draft_keyboard(),
                    )
                    return
                pending["step"] = "source_link"
                context.user_data[_STATE_PENDING_CREATE] = pending
                await self._safe_edit_message_text(
                    query,
                    "Новый пост: шаг 4 из 5\n\n"
                    "Если есть статья, пост или материал-источник, пришлите ссылку одним сообщением.\n"
                    "Если ссылки нет, нажмите «Без ссылки».",
                    reply_markup=self._create_link_keyboard(),
                )
                return

            if data == "cm:clear":
                pending = dict(context.user_data.get(_STATE_PENDING_CREATE) or {})
                step = str(pending.get("step") or "")
                if step == "media":
                    pending["media_urls"] = []
                    context.user_data[_STATE_PENDING_CREATE] = pending
                    await self._safe_edit_message_text(
                        query,
                        "Новый пост: шаг 3 из 5\n\n"
                        "Медиа очищено. Пришлите изображение/видео для поста или нажмите «Без медиа».",
                        reply_markup=self._create_media_keyboard(can_clear=False, media_count=0, editing=False),
                    )
                    return
                draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
                if not draft:
                    await query.message.reply_text("Черновик не найден. Запустите создание заново.")
                    return
                draft["media_urls"] = []
                context.user_data[_STATE_DRAFT_CREATE] = draft
                context.user_data.pop(_STATE_PENDING_CREATE, None)
                await self._safe_edit_message_text(
                    query,
                    self._render_create_preview(draft),
                    reply_markup=self._create_draft_keyboard(),
                )
                return

            if data == "cl:skip":
                pending = dict(context.user_data.get(_STATE_PENDING_CREATE) or {})
                draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
                step = str(pending.get("step") or "")
                if step == "edit_link" and draft:
                    context.user_data.pop(_STATE_PENDING_CREATE, None)
                    await self._safe_edit_message_text(
                        query,
                        self._render_create_preview(draft),
                        reply_markup=self._create_draft_keyboard(),
                    )
                    return
                pending["step"] = "source"
                context.user_data[_STATE_PENDING_CREATE] = pending
                await self._safe_edit_message_text(
                    query,
                    "Новый пост: шаг 5 из 5\n\n"
                    "Пришлите исходный материал: тезисы, текст, заметки или Telegram-транскриб одним сообщением.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("❌ Отменить", callback_data="cn:cancel")]]
                    ),
                )
                return

            if data == "cl:clear":
                draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
                if not draft:
                    await query.message.reply_text("Черновик не найден. Запустите создание заново.")
                    return
                draft["source_url"] = ""
                context.user_data[_STATE_DRAFT_CREATE] = draft
                context.user_data.pop(_STATE_PENDING_CREATE, None)
                await self._safe_edit_message_text(
                    query,
                    self._render_create_preview(draft),
                    reply_markup=self._create_draft_keyboard(),
                )
                return

            if data == "cn:cancel":
                context.user_data.pop(_STATE_PENDING_CREATE, None)
                context.user_data.pop(_STATE_DRAFT_CREATE, None)
                controls = self._load_controls(force_refresh=True)
                counts, _ = await self._queue_snapshot()
                await self._safe_edit_message_text(
                    query,
                    await self._panel_text(controls),
                    reply_markup=self._workspace_keyboard(counts),
                )
                return

            if data.startswith("ce:"):
                draft = context.user_data.get(_STATE_DRAFT_CREATE)
                if not draft:
                    await query.message.reply_text("Активный черновик не найден. Запустите создание поста заново.")
                    return

                _, action = data.split(":", maxsplit=1)
                if action == "kind":
                    context.user_data[_STATE_PENDING_CREATE] = {
                        "mode": str(draft.get("mode") or "manual"),
                        "step": "edit_kind",
                    }
                    await self._safe_edit_message_text(
                        query,
                        "Выберите новый тип поста.",
                        reply_markup=self._create_kind_keyboard(),
                    )
                    return
                if action == "theme":
                    context.user_data[_STATE_PENDING_CREATE] = {
                        "mode": str(draft.get("mode") or "manual"),
                        "step": "edit_theme",
                    }
                    await self._safe_edit_message_text(
                        query,
                        "Выберите новую тематику поста.",
                        reply_markup=self._create_theme_keyboard(),
                    )
                    return
                if action == "media":
                    context.user_data[_STATE_PENDING_CREATE] = {
                        "mode": str(draft.get("mode") or "manual"),
                        "step": "edit_media",
                    }
                    await self._safe_edit_message_text(
                        query,
                        "Пришлите новое изображение/видео для поста или нажмите «Убрать медиа».",
                        reply_markup=self._create_media_keyboard(can_clear=bool(draft.get("media_urls"))),
                    )
                    return
                if action == "link":
                    context.user_data[_STATE_PENDING_CREATE] = {
                        "mode": str(draft.get("mode") or "manual"),
                        "step": "edit_link",
                    }
                    await self._safe_edit_message_text(
                        query,
                        "Пришлите новую ссылку на источник одним сообщением или нажмите «Без ссылки».",
                        reply_markup=self._create_link_keyboard(
                            can_clear=bool(draft.get("source_url")),
                            cancel_callback="cd:view",
                        ),
                    )
                    return
                if action == "source":
                    context.user_data[_STATE_PENDING_CREATE] = {
                        "mode": str(draft.get("mode") or "manual"),
                        "step": "edit_source",
                    }
                    await self._safe_edit_message_text(
                        query,
                        "Пришлите новый исходный материал: тезисы, текст или Telegram-транскриб.",
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("❌ Отменить", callback_data="cd:view")]]
                        ),
                    )
                    return
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

            if data == "cr:lastfirst":
                draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
                media_urls = list(draft.get("media_urls") or [])
                if len(media_urls) < 2:
                    await query.answer("Недостаточно медиа для перестановки", show_alert=False)
                    return
                media_urls.insert(0, media_urls.pop())
                draft["media_urls"] = media_urls
                context.user_data[_STATE_DRAFT_CREATE] = draft
                await self._safe_edit_message_text(
                    query,
                    self._render_create_preview(draft),
                    reply_markup=self._create_draft_keyboard(),
                )
                return

            if data == "cr:reverse":
                draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
                media_urls = list(draft.get("media_urls") or [])
                if len(media_urls) < 2:
                    await query.answer("Недостаточно медиа для перестановки", show_alert=False)
                    return
                draft["media_urls"] = list(reversed(media_urls))
                context.user_data[_STATE_DRAFT_CREATE] = draft
                await self._safe_edit_message_text(
                    query,
                    self._render_create_preview(draft),
                    reply_markup=self._create_draft_keyboard(),
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
                self._load_controls(force_refresh=True)
                counts, next_publish = await self._queue_snapshot()
                await self._safe_edit_message_text(
                    query,
                    self._workspace_text(counts, next_publish),
                    reply_markup=self._workspace_keyboard(counts),
                )
                return

            if data == "sections":
                counts, next_publish = await self._queue_snapshot()
                await self._safe_edit_message_text(
                    query,
                    self._workspace_text(counts, next_publish),
                    reply_markup=self._workspace_keyboard(counts),
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

            if data == "sec:system":
                counts, next_publish = await self._queue_snapshot()
                await self._safe_edit_message_text(
                    query,
                    self._system_text(counts, next_publish),
                    reply_markup=self._system_keyboard(),
                )
                return

            if data == "sec:help":
                await self._safe_edit_message_text(
                    query,
                    self._help_text(),
                    reply_markup=self._system_keyboard(),
                )
                return

            if data == "sec:autoqueue":
                total, rows, overdue = self._load_auto_queue("all", 0, "all")
                await self._safe_edit_message_text(
                    query,
                    self._auto_queue_text(total, rows, 0, overdue, "all", "all"),
                    reply_markup=self._auto_queue_keyboard(total, rows, 0, "all", "all"),
                )
                return

            if data.startswith("aq:"):
                queue_filter, theme_filter, offset = _parse_auto_queue_callback(data)
                total, rows, overdue = self._load_auto_queue(queue_filter, offset, theme_filter)
                await self._safe_edit_message_text(
                    query,
                    self._auto_queue_text(total, rows, offset, overdue, queue_filter, theme_filter),
                    reply_markup=self._auto_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
                )
                return

            if data == "sch:menu":
                await self._safe_edit_message_text(
                    query,
                    self._schedule_settings_text(),
                    reply_markup=self._schedule_settings_keyboard(),
                )
                return

            if data == "lt:menu":
                await self._safe_edit_message_text(
                    query,
                    self._longread_topics_text(),
                    reply_markup=self._longread_topics_keyboard(),
                )
                return

            if data.startswith("lt:toggle:"):
                index = int(data.split(":")[-1]) - 1
                if index < 0 or index >= len(_LONGREAD_TOPIC_LIBRARY):
                    await query.answer("Неизвестная тема лонгрида.", show_alert=True)
                    return
                topic = _LONGREAD_TOPIC_LIBRARY[index]
                row = self._controls_lookup(force_refresh=True).get("news.schedule.longread", {})
                config = dict(row.get("config") or {})
                current_topics = [str(item).strip() for item in config.get("topics", []) if str(item).strip()]
                if not current_topics:
                    current_topics = list(self._longread_topics_active(force_refresh=True))
                if topic in current_topics and len(current_topics) == 1:
                    await query.answer("Нужна хотя бы одна активная тема лонгрида.", show_alert=True)
                    return
                if topic in current_topics:
                    current_topics = [item for item in current_topics if item != topic]
                else:
                    current_topics.append(topic)
                config["topics"] = [item for item in _LONGREAD_TOPIC_LIBRARY if item in current_topics]
                payload = {
                    "scope": "news",
                    "title": row.get("title") or "Воскресный лонгрид",
                    "description": row.get("description") or "Автоматический воскресный лонгрид по одной из тематик канала.",
                    "enabled": bool(row.get("enabled", True)),
                    "config": config,
                }
                self.admin_client.update_automation_control("news.schedule.longread", payload).raise_for_status()
                self._invalidate_controls_cache()
                await self._safe_edit_message_text(
                    query,
                    self._longread_topics_text(),
                    reply_markup=self._longread_topics_keyboard(),
                )
                return

            if data == "lt:reset":
                row = self._controls_lookup(force_refresh=True).get("news.schedule.longread", {})
                config = dict(row.get("config") or {})
                config["topics"] = list(_LONGREAD_TOPIC_LIBRARY)
                payload = {
                    "scope": "news",
                    "title": row.get("title") or "Воскресный лонгрид",
                    "description": row.get("description") or "Автоматический воскресный лонгрид по одной из тематик канала.",
                    "enabled": bool(row.get("enabled", True)),
                    "config": config,
                }
                self.admin_client.update_automation_control("news.schedule.longread", payload).raise_for_status()
                self._invalidate_controls_cache()
                await self._safe_edit_message_text(
                    query,
                    self._longread_topics_text(),
                    reply_markup=self._longread_topics_keyboard(),
                )
                return

            if data.startswith("sch:view:"):
                _, _, alias = data.split(":", maxsplit=2)
                await self._safe_edit_message_text(
                    query,
                    self._schedule_detail_text(alias),
                    reply_markup=self._schedule_detail_keyboard(alias),
                )
                return

            if data.startswith("sch:toggle:"):
                _, _, alias = data.split(":", maxsplit=2)
                meta = schedule_alias_meta(alias)
                control_key = schedule_control_key(alias)
                current_row = self._controls_lookup(force_refresh=True).get(control_key, {})
                payload = {
                    "scope": "news",
                    "title": meta["label"],
                    "description": f"Управление слотом: {meta['window']}",
                    "enabled": not bool(current_row.get("enabled", True)),
                    "config": dict(current_row.get("config") or {}),
                }
                response = self.admin_client.update_automation_control(control_key, payload)
                response.raise_for_status()
                self._invalidate_controls_cache()
                await self._safe_edit_message_text(
                    query,
                    self._schedule_detail_text(alias),
                    reply_markup=self._schedule_detail_keyboard(alias),
                )
                return

            if data.startswith("sch:set:"):
                _, _, alias, token = data.split(":", maxsplit=3)
                option_value = f"{token[:2]}:{token[2:4]}"
                meta = schedule_alias_meta(alias)
                control_key = schedule_control_key(alias)
                current_row = self._controls_lookup(force_refresh=True).get(control_key, {})
                current_config = dict(current_row.get("config") or {})
                current_config["selected_time"] = option_value
                payload = {
                    "scope": "news",
                    "title": meta["label"],
                    "description": f"Управление слотом: {meta['window']}",
                    "enabled": bool(current_row.get("enabled", True)),
                    "config": current_config,
                }
                response = self.admin_client.update_automation_control(control_key, payload)
                response.raise_for_status()
                self._invalidate_controls_cache()
                await self._safe_edit_message_text(
                    query,
                    self._schedule_detail_text(alias),
                    reply_markup=self._schedule_detail_keyboard(alias),
                )
                return

            if data == "int:menu":
                await self._safe_edit_message_text(
                    query,
                    self._interval_settings_text(),
                    reply_markup=self._interval_settings_keyboard(),
                )
                return

            if data.startswith("int:view:"):
                _, _, kind = data.split(":", maxsplit=2)
                if kind not in _INTERVAL_SETTING_KINDS:
                    await query.answer("Неизвестная настройка интервала.", show_alert=True)
                    return
                await self._safe_edit_message_text(
                    query,
                    self._interval_detail_text(kind),
                    reply_markup=self._interval_detail_keyboard(kind),
                )
                return

            if data.startswith("int:set:"):
                _, _, kind, raw_value = data.split(":", maxsplit=3)
                if kind not in _INTERVAL_SETTING_KINDS:
                    await query.answer("Неизвестная настройка интервала.", show_alert=True)
                    return
                if kind == "publish":
                    value = int(raw_value)
                    row = self._publish_control_row(force_refresh=True)
                    config = dict(row.get("config") or {})
                    config["interval_seconds"] = value
                    payload = {
                        "scope": "news",
                        "title": row.get("title") or "Публикация в Telegram (news.publish)",
                        "description": row.get("description") or "Автопаблишер scheduled_posts в Telegram-канал.",
                        "enabled": bool(row.get("enabled", True)),
                        "config": config,
                    }
                    response = self.admin_client.update_automation_control("news.publish.enabled", payload)
                    response.raise_for_status()
                elif kind in {"telegram_morning", "telegram_evening", "telegram_limit"}:
                    row = self._telegram_ingest_control_row(force_refresh=True)
                    config = dict(row.get("config") or {})
                    if kind == "telegram_morning":
                        value = f"{raw_value[:2]}:{raw_value[2:]}"
                        config["morning_time"] = value
                    elif kind == "telegram_evening":
                        value = f"{raw_value[:2]}:{raw_value[2:]}"
                        config["evening_time"] = value
                    else:
                        value = int(raw_value)
                        config["fetch_limit"] = max(10, min(value, 200))
                    payload = {
                        "scope": "news",
                        "title": row.get("title") or "Telegram парсер (news.telegram_ingest)",
                        "description": row.get("description")
                        or "Отдельный Telethon-парсер Telegram-каналов.",
                        "enabled": bool(row.get("enabled", True)),
                        "config": config,
                    }
                    response = self.admin_client.update_automation_control(
                        "news.telegram_ingest.enabled",
                        payload,
                    )
                    response.raise_for_status()
                else:
                    row = self._generate_control_row(force_refresh=True)
                    config = dict(row.get("config") or {})
                    if kind == "generate_morning":
                        value = f"{raw_value[:2]}:{raw_value[2:]}"
                        config["morning_time"] = value
                    elif kind == "generate_evening":
                        value = f"{raw_value[:2]}:{raw_value[2:]}"
                        config["evening_time"] = value
                    elif kind == "retention":
                        value = int(raw_value)
                        config["retention_days"] = value
                    elif kind == "broad_ai":
                        value = int(raw_value)
                        config["broad_ai_limit"] = value
                    else:
                        value = int(raw_value)
                        config["generate_limit"] = value
                    payload = {
                        "scope": "news",
                        "title": row.get("title") or "Генерация контента (news.generate)",
                        "description": row.get("description") or "Автогенерация драфтов из источников по двум слотам в сутки.",
                        "enabled": bool(row.get("enabled", True)),
                        "config": config,
                    }
                    response = self.admin_client.update_automation_control("news.generate.enabled", payload)
                    response.raise_for_status()
                self._invalidate_controls_cache()
                await self._safe_edit_message_text(
                    query,
                    self._interval_detail_text(kind),
                    reply_markup=self._interval_detail_keyboard(kind),
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
                self._invalidate_controls_cache()
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
                self._invalidate_controls_cache()
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
                generation_counts = self._generation_theme_stats()
                await self._safe_edit_message_text(
                    query,
                    self._themes_text(counts, generation_counts),
                    reply_markup=self._themes_keyboard(counts, generation_counts),
                )
                return

            if data == "thm:daily":
                generation_counts = self._generation_theme_stats()
                await self._safe_edit_message_text(
                    query,
                    self._themes_daily_text(generation_counts),
                    reply_markup=self._themes_daily_keyboard(generation_counts),
                )
                return

            if data == "thm:archive":
                counts = self._theme_stats()
                await self._safe_edit_message_text(
                    query,
                    self._themes_archive_text(counts),
                    reply_markup=self._themes_archive_keyboard(counts),
                )
                return

            if data.startswith("gt:"):
                _, theme_key = data.split(":", maxsplit=1)
                if theme_key not in GENERATION_THEME_DEFS:
                    await query.answer("Неизвестная контент-тема.", show_alert=True)
                    return
                row = self._generate_control_row(force_refresh=True)
                config = dict(row.get("config") or {})
                enabled_themes = self._enabled_generation_theme_keys(force_refresh=True)
                if theme_key in enabled_themes and len(enabled_themes) == 1:
                    await query.answer("Нужна хотя бы одна активная тема генерации.", show_alert=True)
                    return
                if theme_key in enabled_themes:
                    enabled_themes.remove(theme_key)
                else:
                    enabled_themes.add(theme_key)
                config["enabled_themes"] = [key for key in generation_theme_keys() if key in enabled_themes]
                payload = {
                    "scope": "news",
                    "title": row.get("title") or "Генерация контента (news.generate)",
                    "description": row.get("description") or "Автогенерация драфтов из источников по двум слотам в сутки.",
                    "enabled": bool(row.get("enabled", True)),
                    "config": config,
                }
                self.admin_client.update_automation_control("news.generate.enabled", payload).raise_for_status()
                self._invalidate_controls_cache()
                generation_counts = self._generation_theme_stats()
                await self._safe_edit_message_text(
                    query,
                    self._themes_daily_text(generation_counts),
                    reply_markup=self._themes_daily_keyboard(generation_counts),
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
                    f"Подбираю {limit} кандидатов и сразу сохраняю AI-драфты в «На проверке». Это может занять до минуты...",
                    reply_markup=InlineKeyboardMarkup([[_inline_button("❌ Отменить", callback_data="sec:generate")]]),
                )
                result = await asyncio.to_thread(collect_generation_previews, limit)
                created_posts, duplicates, failed = await asyncio.to_thread(
                    self._save_generation_previews_to_review,
                    result.previews,
                )
                context.user_data.pop(_STATE_GENERATION_PREVIEWS, None)
                total, rows = self._load_review_posts("ai", 0)
                if created_posts:
                    await self._safe_edit_message_text(
                        query,
                        (
                            f"Готово: {len(created_posts)} AI-драфт(ов) сразу отправлены в «На проверке».\n"
                            f"Дубликатов пропущено: {duplicates}\n"
                            f"Ошибок сохранения: {failed}\n\n"
                            + self._review_posts_text(total, rows, 0, "ai")
                        ),
                        reply_markup=self._review_posts_keyboard(total, rows, 0, "ai"),
                    )
                    return
                controls = self._controls_map(force_refresh=True)
                await self._safe_edit_message_text(
                    query,
                    (
                        "Новых AI-драфтов для сохранения не появилось.\n"
                        f"Дубликатов пропущено: {duplicates}\n"
                        f"Ошибок сохранения: {failed}\n\n"
                        + self._generation_text(controls)
                    ),
                    reply_markup=self._generation_keyboard(),
                )
                return

            if data == "gen:clear":
                context.user_data.pop(_STATE_GENERATION_PREVIEWS, None)
                controls = self._controls_map(force_refresh=True)
                await self._safe_edit_message_text(
                    query,
                    self._generation_text(controls),
                    reply_markup=self._generation_keyboard(),
                )
                return

            if data.startswith("gen:list:"):
                total, rows = self._load_review_posts("all", 0)
                await self._safe_edit_message_text(
                    query,
                    "Временные preview-списки больше не используются.\n\n" + self._review_posts_text(total, rows, 0, "all"),
                    reply_markup=self._review_posts_keyboard(total, rows, 0, "all"),
                )
                return

            if data.startswith("gen:view:"):
                total, rows = self._load_review_posts("all", 0)
                await self._safe_edit_message_text(
                    query,
                    "Временные preview-карточки отключены.\n\nВсе AI-драфты сразу создаются в «На проверке».\n\n"
                    + self._review_posts_text(total, rows, 0, "all"),
                    reply_markup=self._review_posts_keyboard(total, rows, 0, "all"),
                )
                return

            if data.startswith("gen:save:"):
                total, rows = self._load_review_posts("all", 0)
                await self._safe_edit_message_text(
                    query,
                    "AI-драфты уже создаются напрямую в «На проверке».\n\n" + self._review_posts_text(total, rows, 0, "all"),
                    reply_markup=self._review_posts_keyboard(total, rows, 0, "all"),
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

            if data == "preset:twice_daily":
                generate_row = self._generate_control_row(force_refresh=True)
                generate_config = dict(generate_row.get("config") or {})
                generate_config.update(
                    {
                        "morning_time": settings.news_generate_morning_slot,
                        "evening_time": settings.news_generate_evening_slot,
                        "generate_limit": 5,
                        "retention_days": 3,
                        "broad_ai_limit": 1,
                    }
                )
                generate_payload = {
                    "scope": "news",
                    "title": generate_row.get("title") or "Генерация контента (news.generate)",
                    "description": generate_row.get("description") or "Автогенерация драфтов из источников по двум слотам в сутки.",
                    "enabled": True,
                    "config": generate_config,
                }
                self.admin_client.update_automation_control("news.generate.enabled", generate_payload).raise_for_status()

                publish_row = self._publish_control_row(force_refresh=True)
                publish_config = dict(publish_row.get("config") or {})
                publish_config["interval_seconds"] = int(settings.news_publish_interval_seconds)
                publish_payload = {
                    "scope": "news",
                    "title": publish_row.get("title") or "Публикация в Telegram (news.publish)",
                    "description": publish_row.get("description") or "Автопаблишер scheduled_posts в Telegram-канал.",
                    "enabled": True,
                    "config": publish_config,
                }
                self.admin_client.update_automation_control("news.publish.enabled", publish_payload).raise_for_status()

                ingest_row = self._telegram_ingest_control_row(force_refresh=True)
                ingest_config = dict(ingest_row.get("config") or {})
                ingest_config.update(
                    {
                        "morning_time": settings.news_telegram_ingest_morning_slot,
                        "evening_time": settings.news_telegram_ingest_evening_slot,
                        "fetch_limit": settings.telegram_fetch_limit,
                    }
                )
                ingest_payload = {
                    "scope": "news",
                    "title": ingest_row.get("title") or "Telegram парсер (news.telegram_ingest)",
                    "description": ingest_row.get("description")
                    or "Отдельный Telethon-парсер Telegram-каналов.",
                    "enabled": True,
                    "config": ingest_config,
                }
                self.admin_client.update_automation_control(
                    "news.telegram_ingest.enabled",
                    ingest_payload,
                ).raise_for_status()

                self._invalidate_controls_cache()
                controls = self._load_controls(force_refresh=True)
                await self._safe_edit_message_text(
                    query,
                    "Применен пресет автопилота:\n"
                    f"• telegram-парсер: {settings.news_telegram_ingest_morning_slot} и {settings.news_telegram_ingest_evening_slot}\n"
                    f"• генерация: {settings.news_generate_morning_slot} и {settings.news_generate_evening_slot}\n"
                    "• лимит: 5\n"
                    "• хранение review: 3 дня\n"
                    "• broad-ai лимит: 1\n"
                    f"• интервал автопубликации: {_humanize_interval(settings.news_publish_interval_seconds)}\n\n"
                    + self._controls_text(controls),
                    reply_markup=self._automation_keyboard(controls),
                )
                return

            if data.startswith("fa:"):
                enabled = data.split(":", maxsplit=1)[1] == "1"
                for key in ("news.generate.enabled", "news.telegram_ingest.enabled", "news.publish.enabled"):
                    row = self._controls_lookup(force_refresh=True).get(key, {})
                    payload = {
                        "scope": "news",
                        "title": row.get("title") or key,
                        "description": row.get("description") or "",
                        "enabled": enabled,
                        "config": dict(row.get("config") or {}),
                    }
                    self.admin_client.update_automation_control(key, payload).raise_for_status()
                self._invalidate_controls_cache()
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
                payload = response.json()
                await self._safe_edit_message_text(
                    query,
                    _worker_list_text(payload),
                    reply_markup=self._workers_keyboard(payload),
                )
                return

            if data.startswith("wrk:"):
                token = data.split(":", maxsplit=1)[1]
                worker_id = _worker_id_from_callback_token(token)
                if not worker_id:
                    await query.answer("Некорректный worker_id", show_alert=True)
                    return
                response = self.admin_client.workers_activity(worker_id, hours=24, limit=30)
                response.raise_for_status()
                await self._safe_edit_message_text(
                    query,
                    _format_worker_activity(response.json()),
                    reply_markup=self._worker_activity_keyboard(worker_id),
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
                queue_filter, theme_filter, offset = _parse_manual_queue_callback(data)
                total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset, theme_filter=theme_filter)
                await self._safe_edit_message_text(query, 
                    self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total, theme_filter),
                    reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
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
                if status == "review":
                    total, rows = self._load_review_posts("all", offset=offset)
                    await self._safe_edit_message_text(
                        query,
                        self._review_posts_text(total, rows, offset, "all"),
                        reply_markup=self._review_posts_keyboard(total, rows, offset, "all"),
                    )
                    return
                total, rows = self._load_posts(status=status, offset=offset)
                await self._safe_edit_message_text(query, 
                    self._posts_text(total, rows, offset, status),
                    reply_markup=self._posts_keyboard(total, rows, offset, status),
                )
                return

            if data.startswith("rv:"):
                review_filter, kind_filter, theme_filter, offset = _parse_review_filter_callback(data)
                total, rows = self._load_review_posts(review_filter, offset, kind_filter, theme_filter)
                await self._safe_edit_message_text(
                    query,
                    self._review_posts_text(total, rows, offset, review_filter, kind_filter, theme_filter),
                    reply_markup=self._review_posts_keyboard(total, rows, offset, review_filter, kind_filter, theme_filter),
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
                if _is_auto_queue_context(status):
                    queue_filter, theme_filter = _auto_queue_filters_from_context(status)
                    total, rows, overdue = self._load_auto_queue(queue_filter, offset, theme_filter)
                    await self._safe_edit_message_text(
                        query,
                        "Пост удален, негативный feedback сохранен.\n\n"
                        + self._auto_queue_text(total, rows, offset, overdue, queue_filter, theme_filter),
                        reply_markup=self._auto_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
                    )
                    return
                if _is_manual_queue_context(status):
                    queue_filter, theme_filter = _queue_filters_from_context(status)
                    total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset, theme_filter=theme_filter)
                    await self._safe_edit_message_text(
                        query,
                        "Пост удален, негативный feedback сохранен.\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total, theme_filter),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
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
                if _is_auto_queue_context(status):
                    queue_filter, theme_filter = _auto_queue_filters_from_context(status)
                    total, rows, overdue = self._load_auto_queue(queue_filter, 0, theme_filter)
                    await self._safe_edit_message_text(
                        query,
                        "Пост переведён в готовые (scheduled).\n\n"
                        + self._auto_queue_text(total, rows, 0, overdue, queue_filter, theme_filter),
                        reply_markup=self._auto_queue_keyboard(total, rows, 0, queue_filter, theme_filter),
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
                if _is_auto_queue_context(status):
                    queue_filter, theme_filter = _auto_queue_filters_from_context(status)
                    total, rows, overdue = self._load_auto_queue(queue_filter, 0, theme_filter)
                    await self._safe_edit_message_text(
                        query,
                        "Пост переведён в проверку (review).\n\n"
                        + self._auto_queue_text(total, rows, 0, overdue, queue_filter, theme_filter),
                        reply_markup=self._auto_queue_keyboard(total, rows, 0, queue_filter, theme_filter),
                    )
                    return
                total, rows = self._load_review_posts("all", 0)
                await self._safe_edit_message_text(
                    query,
                    "Пост переведён в проверку (review).\n\n" + self._review_posts_text(total, rows, 0, "all"),
                    reply_markup=self._review_posts_keyboard(total, rows, 0, "all"),
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
                context.user_data.pop(_STATE_DRAFT_PUBLISH, None)
                context.user_data.pop(_STATE_PENDING_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_PENDING_BATCH_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_BATCH_PUBLISH, None)
                await self._safe_edit_message_text(query, "Публикуем пост...", reply_markup=None)
                await self._publish_now(context, post_id)
                self._invalidate_post_caches()
                if _is_manual_queue_context(status):
                    queue_filter, theme_filter = _queue_filters_from_context(status)
                    total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset, theme_filter=theme_filter)
                    await self._safe_edit_message_text(
                        query,
                        "Пост успешно опубликован вручную.\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total, theme_filter),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
                    )
                elif _is_auto_queue_context(status):
                    queue_filter, theme_filter = _auto_queue_filters_from_context(status)
                    total, rows, overdue = self._load_auto_queue(queue_filter, offset, theme_filter)
                    await self._safe_edit_message_text(
                        query,
                        "Пост успешно опубликован вручную.\n\n"
                        + self._auto_queue_text(total, rows, offset, overdue, queue_filter, theme_filter),
                        reply_markup=self._auto_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
                    )
                elif _is_source_context(status):
                    source_key = _source_from_context(status)
                    total, rows = self._load_source_posts(source_key, offset)
                    await self._safe_edit_message_text(
                        query,
                        "Пост успешно опубликован вручную.\n\n"
                        + self._source_posts_text(source_key, total, rows, offset),
                        reply_markup=self._source_posts_keyboard(source_key, total, rows, offset),
                    )
                elif _is_theme_context(status):
                    pillar = _theme_from_context(status)
                    total, rows = self._load_theme_posts(pillar, offset)
                    await self._safe_edit_message_text(
                        query,
                        "Пост успешно опубликован вручную.\n\n"
                        + self._theme_posts_text(pillar, total, rows, offset),
                        reply_markup=self._theme_posts_keyboard(pillar, total, rows, offset),
                    )
                elif _is_calendar_context(status):
                    day_key = _calendar_date_from_context(status)
                    rows = self._calendar_day_rows(day_key)
                    await self._safe_edit_message_text(
                        query,
                        "Пост успешно опубликован вручную.\n\n" + self._calendar_day_text(day_key, rows),
                        reply_markup=self._calendar_day_keyboard(day_key, rows),
                    )
                else:
                    total, rows = self._load_posts(status=status, offset=offset)
                    await self._safe_edit_message_text(
                        query,
                        "Пост успешно опубликован вручную.\n\n" + self._posts_text(total, rows, offset, status),
                        reply_markup=self._posts_keyboard(total, rows, offset, status),
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
                context.user_data.pop(_STATE_PENDING_PUBLISH_REASON, None)
                context.user_data.pop(_STATE_DRAFT_PUBLISH, None)
                await self._safe_edit_message_text(query, "Публикуем пост...", reply_markup=None)
                await self._publish_now(context, post_id)
                if _is_manual_queue_context(status):
                    queue_filter, theme_filter = _queue_filters_from_context(status)
                    total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset, theme_filter=theme_filter)
                    await self._safe_edit_message_text(query, 
                        "Пост успешно опубликован вручную.\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total, theme_filter),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
                    )
                elif _is_auto_queue_context(status):
                    queue_filter, theme_filter = _auto_queue_filters_from_context(status)
                    total, rows, overdue = self._load_auto_queue(queue_filter, offset, theme_filter)
                    await self._safe_edit_message_text(
                        query,
                        "Пост успешно опубликован вручную.\n\n"
                        + self._auto_queue_text(total, rows, offset, overdue, queue_filter, theme_filter),
                        reply_markup=self._auto_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
                    )
                elif _is_source_context(status):
                    domain = _source_from_context(status)
                    total, rows = self._load_source_posts(domain, offset)
                    await self._safe_edit_message_text(
                        query,
                        "Пост успешно опубликован вручную.\n\n"
                        + self._source_posts_text(domain, total, rows, offset),
                        reply_markup=self._source_posts_keyboard(domain, total, rows, offset),
                    )
                elif _is_theme_context(status):
                    pillar = _theme_from_context(status)
                    total, rows = self._load_theme_posts(pillar, offset)
                    await self._safe_edit_message_text(
                        query,
                        "Пост успешно опубликован вручную.\n\n"
                        + self._theme_posts_text(pillar, total, rows, offset),
                        reply_markup=self._theme_posts_keyboard(pillar, total, rows, offset),
                    )
                elif _is_calendar_context(status):
                    day_key = _calendar_date_from_context(status)
                    rows = self._calendar_day_rows(day_key)
                    await self._safe_edit_message_text(
                        query,
                        "Пост успешно опубликован вручную.\n\n"
                        + self._calendar_day_text(day_key, rows),
                        reply_markup=self._calendar_day_keyboard(day_key, rows),
                    )
                else:
                    total, rows = self._load_posts(status=status, offset=offset)
                    await self._safe_edit_message_text(query, 
                        "Пост успешно опубликован вручную.\n\n"
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

            if data.startswith("pf:"):
                _, post_id, status, offset_raw = data.split(":", maxsplit=3)
                offset = int(offset_raw)
                await self._safe_edit_message_text(
                    query,
                    "Подождите, формируется футер и обновляется драфт…",
                )
                post = self._get_post(post_id)
                footer_text = self._generate_footer_with_llm(post)
                if not footer_text:
                    raise RuntimeError("LLM не смог предложить footer")
                updated_text = self._apply_footer_to_post_text(str(post.get("text") or ""), footer_text)
                self.client.patch_post(post_id, {"text": updated_text}).raise_for_status()
                self._invalidate_post_caches()
                updated_post = self._get_post(post_id)
                await self._safe_edit_message_text(
                    query,
                    "Footer добавлен в драфт.\n\n" + self._post_card_text(updated_post),
                    reply_markup=self._post_card_keyboard(post_id, status, offset),
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
                    queue_filter, theme_filter = _queue_filters_from_context(status)
                    total, rows, due_total, scheduled_total = self._load_manual_queue(queue_filter=queue_filter, offset=offset, theme_filter=theme_filter)
                    await self._safe_edit_message_text(query, 
                        "Редактирование отменено.\n\n"
                        + self._manual_queue_text(total, rows, offset, queue_filter, due_total, scheduled_total, theme_filter),
                        reply_markup=self._manual_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
                    )
                elif _is_auto_queue_context(status):
                    queue_filter, theme_filter = _auto_queue_filters_from_context(status)
                    total, rows, overdue = self._load_auto_queue(queue_filter, offset, theme_filter)
                    await self._safe_edit_message_text(
                        query,
                        "Редактирование отменено.\n\n"
                        + self._auto_queue_text(total, rows, offset, overdue, queue_filter, theme_filter),
                        reply_markup=self._auto_queue_keyboard(total, rows, offset, queue_filter, theme_filter),
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
            step = str(pending_create.get("step") or "source")
            title = str(pending_create.get("title") or "").strip()
            kind = str(pending_create.get("kind") or "")
            theme = str(pending_create.get("theme") or "")
            source_material = str(pending_create.get("source_material") or "").strip()
            source_url = str(pending_create.get("source_url") or "").strip()

            try:
                if step == "source_link":
                    source_url = message_text
                    context.user_data[_STATE_PENDING_CREATE] = {
                        "mode": mode,
                        "kind": kind,
                        "theme": theme,
                        "step": "source",
                        "source_url": source_url,
                    }
                    await update.effective_message.reply_text(
                        "Новый пост: шаг 5 из 5\n\n"
                        f"Тип: {_manual_post_kind_label(kind)}\n"
                        f"Тема: {_manual_theme_label(theme)}\n\n"
                        + (
                            "Теперь пришлите текстовый транскриб или пересланное сообщение с расшифровкой.\n"
                            "Голосовой файл без текстовой расшифровки бот не соберет."
                            if mode == "transcript"
                            else "Теперь пришлите исходный материал: тезисы, текст, заметки или Telegram-транскриб одним сообщением."
                        ),
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("❌ Отменить", callback_data="cn:cancel")]]
                        ),
                    )
                    return

                if step == "source":
                    source_material = message_text
                    context.user_data[_STATE_PENDING_CREATE] = {
                        "mode": mode,
                        "kind": kind,
                        "theme": theme,
                        "step": "title",
                        "source_material": source_material,
                        "source_url": source_url,
                    }
                    await update.effective_message.reply_text(
                        "Новый пост: шаг 5 из 5\n\n"
                        f"Тип: {_manual_post_kind_label(kind)}\n"
                        f"Тема: {_manual_theme_label(theme)}\n"
                        f"{_manual_post_kind_structure(kind)}\n\n"
                        f"{_manual_post_kind_screen_template(kind)}\n\n"
                        "Пришлите заголовок или тему поста одним сообщением.",
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("❌ Отменить", callback_data="cn:cancel")]]
                        ),
                    )
                    return

                if step == "title":
                    title = message_text
                    media_urls = list(pending_create.get("media_urls") or [])
                    if mode == "manual":
                        draft = {
                            "mode": mode,
                            "kind": kind,
                            "theme": theme,
                            "title": title,
                            "text": source_material,
                            "source_material": source_material,
                            "source_url": source_url,
                            "media_urls": media_urls,
                        }
                        context.user_data[_STATE_DRAFT_CREATE] = draft
                        context.user_data.pop(_STATE_PENDING_CREATE, None)
                        await self._show_create_draft(update.effective_message, draft)
                    else:
                        draft_text = self._draft_post_with_llm(
                            title,
                            source_material,
                            kind,
                            source_mode=mode,
                            theme=theme,
                        )
                        draft = {
                            "mode": mode,
                            "kind": kind,
                            "theme": theme,
                            "title": title,
                            "text": draft_text,
                            "source_material": source_material,
                            "source_url": source_url,
                            "media_urls": media_urls,
                        }
                        payload = self._create_post_payload(draft, status="review", publish_at=datetime.now(timezone.utc))
                        response = self.client.create_scheduled_post(payload)
                        response.raise_for_status()
                        self._invalidate_post_caches()
                        post = response.json()
                        context.user_data.pop(_STATE_DRAFT_CREATE, None)
                        context.user_data.pop(_STATE_PENDING_CREATE, None)
                        await update.effective_message.reply_text(
                            "LLM-черновик сразу сохранен в «На проверке».\n\n" + self._post_card_text(post),
                            reply_markup=self._post_card_keyboard(str(post["id"]), str(post["status"]), 0),
                        )
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
                    elif step == "edit_source":
                        draft["source_material"] = message_text
                    elif step == "edit_link":
                        draft["source_url"] = message_text
                    elif step == "edit_ai":
                        draft["text"] = self._rewrite_with_llm(
                            str(draft.get("text") or ""),
                            f"{message_text}\n\nТип поста: {_manual_post_kind_label(str(draft.get('kind') or ''))}\nТема: {_manual_theme_label(str(draft.get('theme') or ''))}",
                        )
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
            if _button_text_equals(message_text, _MAIN_MENU_WORKSPACE) or _button_text_equals(message_text, "🏠 Панель"):
                await self.cmd_panel(update, context)
                return
            if _button_text_equals(message_text, _MAIN_MENU_CREATE):
                await self.cmd_new_post(update, context)
                return
            if _button_text_equals(message_text, "🗓 Календарь"):
                await self.cmd_calendar(update, context)
                return
            if _button_text_equals(message_text, "📚 Разделы"):
                await self.cmd_panel(update, context)
                return
            if _button_text_equals(message_text, "ℹ️ Помощь"):
                await self.cmd_help(update, context)
                return
            await update.effective_message.reply_text(
                "Для навигации используйте inline-кнопки в текущем сообщении. Основная точка входа — «Рабочий стол», а ручное создание запускается через «➕ Создать пост».",
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

    async def on_create_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_admin(update):
            return

        pending_create = context.user_data.get(_STATE_PENDING_CREATE)
        if not pending_create:
            return

        step = str(pending_create.get("step") or "")
        if step not in {"media", "edit_media"}:
            return

        message = update.effective_message
        if message is None:
            return

        media_token = _tg_media_token(message)
        if media_token is None:
            await message.reply_text(
                "Для этого шага пришлите изображение, видео или image-документ Telegram.\n"
                "Если медиа не нужно, нажмите «Без медиа».",
                reply_markup=self._create_media_keyboard(can_clear=step == "edit_media"),
            )
            return

        media_kind, media_url = media_token
        if step == "edit_media":
            draft = dict(context.user_data.get(_STATE_DRAFT_CREATE) or {})
            if not draft:
                context.user_data.pop(_STATE_PENDING_CREATE, None)
                await message.reply_text("Черновик не найден. Запустите создание заново.")
                return
            current_media = list(draft.get("media_urls") or [])
            if media_url not in current_media:
                current_media.append(media_url)
            draft["media_urls"] = current_media
            context.user_data[_STATE_DRAFT_CREATE] = draft
            await message.reply_text(
                f"Медиа добавлено: {media_kind}. Сейчас вложений: {len(current_media)}.\n"
                "Можно прислать еще медиа или нажать «Готово».",
                reply_markup=self._create_media_keyboard(
                    can_clear=bool(current_media),
                    media_count=len(current_media),
                    editing=True,
                ),
            )
            return

        next_state = dict(pending_create)
        current_media = list(next_state.get("media_urls") or [])
        if media_url not in current_media:
            current_media.append(media_url)
        next_state["media_urls"] = current_media
        next_state["step"] = "media"
        context.user_data[_STATE_PENDING_CREATE] = next_state
        await message.reply_text(
            "Новый пост: шаг 3 из 5\n\n"
            f"Медиа добавлено: {media_kind}. Сейчас вложений: {len(current_media)}.\n"
            "Можно прислать еще медиа или нажать «Готово».",
            reply_markup=self._create_media_keyboard(
                can_clear=bool(current_media),
                media_count=len(current_media),
                editing=False,
            ),
        )

    async def on_transcript_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_admin(update):
            return

        pending_create = context.user_data.get(_STATE_PENDING_CREATE)
        if not pending_create:
            return

        mode = str(pending_create.get("mode") or "")
        step = str(pending_create.get("step") or "")
        if mode != "transcript" or step != "source":
            return

        await update.effective_message.reply_text(
            "Для режима «из транскриба / voice» нужен текстовый транскриб.\n"
            "Пришлите расшифровку одним сообщением или перешлите сообщение Telegram с уже готовым транскрибом.\n"
            "Сам голосовой файл без текста бот сейчас не расшифровывает.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Отменить", callback_data="cn:cancel")]]
            ),
        )

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
        app.add_handler(CommandHandler("autoqueue", self.cmd_autoqueue))
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
                pattern=_is_calendar_callback,
            )
        )
        app.add_handler(
            CallbackQueryHandler(
                self.cb_create,
                pattern=_is_create_callback,
            )
        )
        app.add_handler(
            CallbackQueryHandler(
                self.cb_controls,
                pattern=_is_controls_callback,
            )
        )
        app.add_handler(
            CallbackQueryHandler(
                self.cb_posts,
                pattern=_is_posts_callback,
            )
        )
        app.add_handler(
            MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, self.on_edit_text)
        )
        app.add_handler(
            MessageHandler(
                (filters.PHOTO | filters.VIDEO | filters.VIDEO_NOTE | filters.Document.ALL) & filters.ChatType.PRIVATE,
                self.on_create_media,
            )
        )
        app.add_handler(
            MessageHandler(
                (filters.VOICE | filters.AUDIO) & filters.ChatType.PRIVATE,
                self.on_transcript_voice,
            )
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
