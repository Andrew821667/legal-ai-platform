from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from aiogram.types import InlineKeyboardButton as _InlineKeyboardButton
from aiogram.types import KeyboardButton as _KeyboardButton

BUTTON_STYLE_PRIMARY = "primary"
BUTTON_STYLE_SUCCESS = "success"
BUTTON_STYLE_DANGER = "danger"
_READER_BUTTON_ICON_ENV = "NEWS_READER_BUTTON_ICON_MAP"
_LOCAL_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _read_env_value(env_file: Path, key: str) -> str:
    if not env_file.exists():
        return ""
    prefix = f"{key}="
    for line in env_file.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if item.startswith(prefix):
            return item[len(prefix):].strip()
    return ""


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


@lru_cache(maxsize=1)
def _button_icon_map() -> dict[str, str]:
    raw = os.getenv(_READER_BUTTON_ICON_ENV, "").strip()
    if not raw:
        raw = _read_env_value(_LOCAL_ENV_FILE, _READER_BUTTON_ICON_ENV)
    return _parse_button_icon_map(raw)


def _infer_icon_key(text: str | None) -> str | None:
    label = (text or "").strip()
    normalized = label.lower()
    if not normalized:
        return None
    exact = {
        "📖 читать полностью": "read_more",
        "👍 полезно": "useful",
        "👎 не интересно": "not_interesting",
        "🎯 да, хочу персональный дайджест!": "digest_accept",
        "❌ пока не интересно": "digest_decline",
    }
    if normalized in exact:
        return exact[normalized]
    contains_rules = (
        ("сохран", "save"),
        ("дайджест", "digest"),
        ("поиск", "search"),
        ("настрой", "settings"),
        ("назад", "back"),
        ("опубликовать", "publish"),
        ("создать", "create"),
        ("поделиться", "share"),
        ("вопрос", "question"),
        ("идея", "idea"),
    )
    for token, key in contains_rules:
        if token in normalized:
            return key
    return None


def _infer_style(text: str | None) -> str | None:
    label = (text or "").strip()
    if not label:
        return None
    normalized = label.lower()
    if label.startswith(("✅", "👍")) or any(
        token in normalized
        for token in (
            "опубликовать",
            "читать полностью",
            "персональный дайджест",
            "сохранить",
            "подтверд",
        )
    ):
        return BUTTON_STYLE_SUCCESS
    if label.startswith(("❌", "🚫", "👎", "🗑")) or any(
        token in normalized
        for token in (
            "отмен",
            "удал",
            "отключ",
            "не интересно",
        )
    ):
        return BUTTON_STYLE_DANGER
    return None


def inline_button(*, text: str, style: str | None = None, icon_custom_emoji_id: str | None = None, **kwargs: Any):
    extra_data = dict(kwargs)
    resolved_style = style or _infer_style(text)
    if icon_custom_emoji_id is None:
        icon_key = _infer_icon_key(text)
        if icon_key:
            icon_custom_emoji_id = _button_icon_map().get(icon_key)
    if resolved_style:
        extra_data["style"] = resolved_style
    if icon_custom_emoji_id:
        extra_data["icon_custom_emoji_id"] = icon_custom_emoji_id
    return _InlineKeyboardButton(text=text, **extra_data)


def reply_button(*, text: str, style: str | None = None, icon_custom_emoji_id: str | None = None, **kwargs: Any):
    extra_data = dict(kwargs)
    resolved_style = style or _infer_style(text)
    if icon_custom_emoji_id is None:
        icon_key = _infer_icon_key(text)
        if icon_key:
            icon_custom_emoji_id = _button_icon_map().get(icon_key)
    if resolved_style:
        extra_data["style"] = resolved_style
    if icon_custom_emoji_id:
        extra_data["icon_custom_emoji_id"] = icon_custom_emoji_id
    return _KeyboardButton(text=text, **extra_data)
