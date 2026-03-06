"""
Shared reader/mini-app analytics vocabulary for bot -> core-api events.
"""

from __future__ import annotations

READER_EVENT_SOURCES: dict[str, str] = {
    "bot": "reader.bot",
    "home": "reader.home",
    "start": "reader.start",
    "nav": "reader.nav",
    "discover": "reader.discover",
    "validate": "reader.validate",
    "solutions": "reader.solutions",
    "profile": "reader.profile",
    "command": "reader.command",
    "article": "reader.article",
    "article_card": "reader.article.card",
    "post": "reader.post",
}

READER_EVENT_ACTIONS: dict[str, str] = {
    "open_miniapp_home": "open.miniapp.home",
    "open_miniapp_content": "open.miniapp.content",
    "open_miniapp_tools": "open.miniapp.tools",
    "open_miniapp_solutions": "open.miniapp.solutions",
    "open_miniapp_profile": "open.miniapp.profile",
    "open_miniapp_resume": "open.miniapp.resume",
}

READER_CTA_TYPES: dict[str, str] = {
    "miniapp_open": "miniapp_open",
    "article_question": "article_question",
    "consultation": "consultation",
}

READER_INTENT_TYPES: dict[str, str] = {
    "consultation": "consultation",
    "followup": "followup",
    "article_question": "article_question",
}
