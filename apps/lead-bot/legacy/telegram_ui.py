from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton as _InlineKeyboardButton
from telegram import KeyboardButton as _KeyboardButton

BUTTON_STYLE_PRIMARY = "primary"
BUTTON_STYLE_SUCCESS = "success"
BUTTON_STYLE_DANGER = "danger"
_LEAD_BUTTON_ICON_ENV = "LEAD_BOT_BUTTON_ICON_MAP"
_LOCAL_ENV_FILE = Path(__file__).resolve().parent / ".env"


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
    raw = os.getenv(_LEAD_BUTTON_ICON_ENV, "").strip()
    if not raw:
        raw = _read_env_value(_LOCAL_ENV_FILE, _LEAD_BUTTON_ICON_ENV)
    return _parse_button_icon_map(raw)


def _infer_icon_key(text: str | None) -> str | None:
    label = (text or "").strip()
    normalized = label.lower()
    if not normalized:
        return None
    exact = {
        "📋 меню услуг": "services",
        "📞 консультация": "consultation",
        "📲 контакт": "contact",
        "👤 мой профиль": "profile",
        "📚 документы": "documents",
        "✉️ личное обращение": "personal",
        "⚙️ админ-панель": "admin",
        "🔄 начать заново": "restart",
        "❓ помощь": "help",
    }
    if normalized in exact:
        return exact[normalized]
    contains_rules = (
        ("заказать консультацию", "consultation"),
        ("отправить телефон", "send_phone"),
        ("оставить номер", "send_phone"),
        ("связаться в telegram", "telegram"),
        ("даю согласие", "consent_accept"),
        ("согласен", "consent_accept"),
        ("отказ", "consent_decline"),
        ("политика", "policy"),
        ("документы", "documents"),
        ("экспорт", "export"),
        ("назад", "back"),
        ("вернуться к боту", "return_bot"),
        ("очист", "cleanup"),
        ("закрыть", "close"),
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
    if label.startswith("✅") or any(
        token in normalized
        for token in (
            "консультац",
            "оставить номер",
            "отправить телефон",
            "связаться",
            "дайджест",
            "сохранить",
            "подтверд",
        )
    ):
        return BUTTON_STYLE_SUCCESS
    if label.startswith(("❌", "🗑", "⛔", "⚠️")) or any(
        token in normalized
        for token in (
            "отказ",
            "отмен",
            "очист",
            "удал",
            "закрыть",
            "отозвать",
        )
    ):
        return BUTTON_STYLE_DANGER
    return None


def _merge_api_kwargs(
    *,
    style: str | None,
    icon_custom_emoji_id: str | None,
    api_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    merged = dict(api_kwargs or {})
    if style:
        merged["style"] = style
    if icon_custom_emoji_id:
        merged["icon_custom_emoji_id"] = icon_custom_emoji_id
    return merged or None


def inline_button(text: str, *args: Any, style: str | None = None, icon_custom_emoji_id: str | None = None, **kwargs: Any):
    api_kwargs = kwargs.pop("api_kwargs", None)
    if icon_custom_emoji_id is None:
        icon_key = _infer_icon_key(text)
        if icon_key:
            icon_custom_emoji_id = _button_icon_map().get(icon_key)
    return _InlineKeyboardButton(
        text,
        *args,
        api_kwargs=_merge_api_kwargs(
            style=style or _infer_style(text),
            icon_custom_emoji_id=icon_custom_emoji_id,
            api_kwargs=api_kwargs,
        ),
        **kwargs,
    )


def reply_button(text: str, *args: Any, style: str | None = None, icon_custom_emoji_id: str | None = None, **kwargs: Any):
    api_kwargs = kwargs.pop("api_kwargs", None)
    if icon_custom_emoji_id is None:
        icon_key = _infer_icon_key(text)
        if icon_key:
            icon_custom_emoji_id = _button_icon_map().get(icon_key)
    return _KeyboardButton(
        text,
        *args,
        api_kwargs=_merge_api_kwargs(
            style=style or _infer_style(text),
            icon_custom_emoji_id=icon_custom_emoji_id,
            api_kwargs=api_kwargs,
        ),
        **kwargs,
    )
