from __future__ import annotations

import re
from typing import Final

MINIAPP_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "action",
        "nav_click",
        "cta_click",
        "content_open",
        "tool_open",
        "solution_open",
        "profile_saved",
        "deeplink_open",
        "deeplink_issued",
    }
)

READER_EVENT_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "miniapp.app",
        "miniapp.topbar",
        "miniapp.home",
        "miniapp.content",
        "miniapp.tools",
        "miniapp.solutions",
        "miniapp.profile",
        "miniapp.flow",
        "miniapp.deeplink",
        "reader.bot",
        "reader.home",
        "reader.start",
        "reader.nav",
        "reader.discover",
        "reader.validate",
        "reader.solutions",
        "reader.profile",
        "reader.command",
        "reader.article",
        "reader.article.card",
        "reader.post",
    }
)

READER_EVENT_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "open.content",
        "open.content_item",
        "open.contract_ai",
        "open.solutions",
        "open.recommended_step",
        "open.onboarding",
        "open.profile",
        "open.history",
        "open.future_tools",
        "open.solutions.for_lawyers",
        "open.solutions.for_business",
        "open.solutions.roadmap",
        "flow.discover",
        "flow.validate",
        "flow.implement",
        "profile.saved",
        "cta.open.assistant",
        "open.miniapp.home",
        "open.miniapp.content",
        "open.miniapp.tools",
        "open.miniapp.solutions",
        "open.miniapp.profile",
        "open.miniapp.resume",
        "open.saved",
        "cta.article_question",
        "cta.consultation",
        "cta.miniapp_open",
        "lead.consultation",
        "lead.followup",
        "lead.article_question",
    }
)

READER_CTA_TYPES: Final[frozenset[str]] = frozenset(
    {
        "consultation",
        "article_question",
        "miniapp_open",
        "discover",
        "validate",
        "implement",
        "assistant_contact",
    }
)

READER_INTENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "consultation",
        "followup",
        "article_question",
        "implementation",
        "audit",
    }
)

MINIAPP_SCREEN_KEY_TO_PATH: Final[dict[str, str]] = {
    "home": "/miniapp",
    "content": "/miniapp/content",
    "tools": "/miniapp/tools",
    "solutions": "/miniapp/solutions",
    "profile": "/miniapp/profile",
}

_SAFE_TOKEN_RE = re.compile(r"[^a-z0-9._-]+")

_EVENT_TYPE_ALIASES: Final[dict[str, str]] = {
    "solutionopen": "solution_open",
    "toolopen": "tool_open",
    "contentopen": "content_open",
}

_SOURCE_ALIASES: Final[dict[str, str]] = {
    "miniapp": "miniapp.app",
    "miniapp_app": "miniapp.app",
    "miniapp_topbar": "miniapp.topbar",
    "miniapp_home": "miniapp.home",
    "miniapp_content": "miniapp.content",
    "miniapp_tools": "miniapp.tools",
    "miniapp_solutions": "miniapp.solutions",
    "miniapp_profile": "miniapp.profile",
    "miniapp_flow": "miniapp.flow",
    "reader_bot": "reader.bot",
    "reader_home": "reader.home",
    "reader_start": "reader.start",
    "reader_nav": "reader.nav",
    "reader_discover": "reader.discover",
    "reader_validate": "reader.validate",
    "reader_solutions": "reader.solutions",
    "reader_profile": "reader.profile",
    "reader_command": "reader.command",
    "reader_article": "reader.article",
    "reader_article_card": "reader.article.card",
    "reader_post": "reader.post",
}

_ACTION_ALIASES: Final[dict[str, str]] = {
    "miniapp_home_open_content": "open.content",
    "miniapp_home_open_contract_ai": "open.contract_ai",
    "miniapp_home_open_solutions": "open.solutions",
    "miniapp_home_open_recommended_step": "open.recommended_step",
    "miniapp_content_open_contract_ai": "open.contract_ai",
    "miniapp_open_onboarding": "open.onboarding",
    "miniapp_open_profile": "open.profile",
    "miniapp_tools_open_contract_ai": "open.contract_ai",
    "miniapp_tools_open_history": "open.history",
    "miniapp_tools_open_future_tools": "open.future_tools",
    "miniapp_solutions_open_for_lawyers": "open.solutions.for_lawyers",
    "miniapp_solutions_open_for_business": "open.solutions.for_business",
    "miniapp_solutions_open_roadmap": "open.solutions.roadmap",
    "miniapp_flow_open_reader_discover": "flow.discover",
    "miniapp_flow_open_contract_ai": "flow.validate",
    "miniapp_flow_open_lead_bot": "flow.implement",
    "miniapp_profile_saved": "profile.saved",
    "miniapp_profile_open_assistant": "cta.open.assistant",
    "reader_home_continue_miniapp": "open.miniapp.resume",
    "reader_discover_open_miniapp": "open.miniapp.content",
    "reader_validate_open_miniapp": "open.miniapp.tools",
    "reader_solutions_open_miniapp": "open.miniapp.solutions",
    "reader_profile_open_miniapp": "open.miniapp.profile",
    "reader_start_open_miniapp_content": "open.miniapp.content",
    "reader_start_open_miniapp_tools": "open.miniapp.tools",
    "reader_start_open_miniapp_solutions": "open.miniapp.solutions",
    "reader_start_open_miniapp_profile": "open.miniapp.profile",
    "reader_nav_open_miniapp": "open.miniapp.home",
    "reader_nav_open_miniapp_content": "open.miniapp.content",
    "reader_nav_open_miniapp_tools": "open.miniapp.tools",
    "reader_nav_open_miniapp_solutions": "open.miniapp.solutions",
    "reader_nav_open_miniapp_profile": "open.miniapp.profile",
    "reader_command_open_miniapp": "open.miniapp.home",
    "reader_article_open_miniapp": "open.miniapp.content",
    "open_saved": "open.saved",
}

_CTA_TYPE_ALIASES: Final[dict[str, str]] = {
    "consult": "consultation",
    "consultation_request": "consultation",
    "article_q": "article_question",
    "miniapp": "miniapp_open",
}

_INTENT_TYPE_ALIASES: Final[dict[str, str]] = {
    "consult": "consultation",
    "consultation_request": "consultation",
    "article_q": "article_question",
}


def _clean_token(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    normalized = normalized.replace("/", ".").replace(":", ".").replace(" ", "_")
    normalized = _SAFE_TOKEN_RE.sub("_", normalized).strip("._-")
    if not normalized:
        return None
    return normalized[:max_len]


def normalize_miniapp_event_type(value: str | None) -> str:
    token = (_clean_token(value, max_len=100) or "action").replace(".", "_")
    token = _EVENT_TYPE_ALIASES.get(token, token)
    if token in MINIAPP_EVENT_TYPES:
        return token
    return "action"


def normalize_reader_source(value: str | None, *, default: str = "miniapp.app") -> str:
    token = _clean_token(value, max_len=64)
    if token is None:
        return default
    token = _SOURCE_ALIASES.get(token, token)
    if token in READER_EVENT_SOURCES:
        return token
    return default


def normalize_reader_action(value: str | None) -> str | None:
    token = _clean_token(value, max_len=120)
    if token is None:
        return None

    if token.startswith("miniapp_content_open."):
        return "open.content_item"
    if token.startswith("open_saved."):
        return "open.saved"

    token = _ACTION_ALIASES.get(token, token)
    if token in READER_EVENT_ACTIONS:
        return token
    return token


def normalize_cta_type(value: str | None) -> str | None:
    token = _clean_token(value, max_len=64)
    if token is None:
        return None
    token = _CTA_TYPE_ALIASES.get(token, token)
    if token in READER_CTA_TYPES:
        return token
    return token


def normalize_cta_context(value: str | None) -> str | None:
    token = _clean_token(value, max_len=64)
    if token is None:
        return None
    token = _SOURCE_ALIASES.get(token, token)
    if token in READER_EVENT_SOURCES:
        return token
    return token


def normalize_intent_type(value: str | None) -> str:
    token = _clean_token(value, max_len=64) or "consultation"
    token = _INTENT_TYPE_ALIASES.get(token, token)
    if token in READER_INTENT_TYPES:
        return token
    return token


def normalize_screen_path(value: str | None) -> str | None:
    token = _clean_token(value, max_len=64)
    if token is None:
        return None
    if token in MINIAPP_SCREEN_KEY_TO_PATH:
        return MINIAPP_SCREEN_KEY_TO_PATH[token]
    if token in {"miniapp", "miniapp.home"}:
        return MINIAPP_SCREEN_KEY_TO_PATH["home"]
    if token in {"miniapp.content"}:
        return MINIAPP_SCREEN_KEY_TO_PATH["content"]
    if token in {"miniapp.tools"}:
        return MINIAPP_SCREEN_KEY_TO_PATH["tools"]
    if token in {"miniapp.solutions"}:
        return MINIAPP_SCREEN_KEY_TO_PATH["solutions"]
    if token in {"miniapp.profile"}:
        return MINIAPP_SCREEN_KEY_TO_PATH["profile"]

    raw = str(value or "").strip().lower()
    if raw.startswith("/miniapp"):
        if raw == "/miniapp":
            return MINIAPP_SCREEN_KEY_TO_PATH["home"]
        if raw.startswith("/miniapp/content"):
            return MINIAPP_SCREEN_KEY_TO_PATH["content"]
        if raw.startswith("/miniapp/tools"):
            return MINIAPP_SCREEN_KEY_TO_PATH["tools"]
        if raw.startswith("/miniapp/solutions"):
            return MINIAPP_SCREEN_KEY_TO_PATH["solutions"]
        if raw.startswith("/miniapp/profile"):
            return MINIAPP_SCREEN_KEY_TO_PATH["profile"]
    return raw[:120] if raw else None


def normalize_screen_key(value: str | None) -> str:
    path = normalize_screen_path(value)
    if path in MINIAPP_SCREEN_KEY_TO_PATH.values():
        for key, candidate in MINIAPP_SCREEN_KEY_TO_PATH.items():
            if candidate == path:
                return key
    return "home"
